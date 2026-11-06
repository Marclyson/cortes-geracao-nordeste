"""Carga dos arquivos mensais do ONS (dados abertos, licença CC BY 4.0) para o schema raw do Postgres.

Cada fonte é publicada como um Parquet por mês num bucket público da AWS. O ONS atualiza o mês
corrente duas vezes por dia (por volta das 12h e das 19h, horário de Brasília) e também regrava meses
já publicados. Por isso a carga compara o ETag do arquivo com o da última carga: se mudou, baixa de
novo e troca as linhas daquele arquivo dentro de uma transação. Rodar duas vezes dá o mesmo resultado.
"""
import io
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

BASE = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset"
DADOS = Path("/opt/airflow/dados/ons")
AGENTE = "cortes-geracao-nordeste/0.1 (projeto de estudo)"

FONTES = {
    "restricao_eolica": {
        "descricao": "Restrição de operação (constrained-off) das usinas eólicas, por usina, a cada 30 min",
        "pasta": "restricao_coff_eolica_tm",
        "arquivo": "RESTRICAO_COFF_EOLICA_{ano}_{mes:02d}.parquet",
        "inicio": "2021-10",
    },
    "restricao_solar": {
        "descricao": "Restrição de operação (constrained-off) das usinas fotovoltaicas, por usina, a cada 30 min",
        "pasta": "restricao_coff_fotovoltaica_tm",
        "arquivo": "RESTRICAO_COFF_FOTOVOLTAICA_{ano}_{mes:02d}.parquet",
        "inicio": "2024-04",
    },
}

TIPOS = [
    (pa.types.is_string, "text"),
    (pa.types.is_large_string, "text"),
    (pa.types.is_boolean, "boolean"),
    (pa.types.is_integer, "bigint"),
    (pa.types.is_floating, "double precision"),
    (pa.types.is_timestamp, "timestamp"),
    (pa.types.is_date, "date"),
]


def meses_entre(inicio, fim):
    """Lista 'AAAA-MM' de inicio a fim, inclusive."""
    ano, mes = map(int, inicio.split("-"))
    ano_fim, mes_fim = map(int, fim.split("-"))
    meses = []
    while (ano, mes) <= (ano_fim, mes_fim):
        meses.append(f"{ano}-{mes:02d}")
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def meses_da_execucao(fonte, referencia, meses_atras=2, desde=None):
    """Meses que uma execução deve conferir: o da referência e os `meses_atras` anteriores.

    Com `desde` ('AAAA-MM'), confere todos os meses dali até a referência (carga histórica).
    Nunca volta antes do primeiro mês publicado da fonte.
    """
    fim = f"{referencia.year}-{referencia.month:02d}"
    if desde:
        inicio = desde
    else:
        ano, mes = referencia.year, referencia.month - meses_atras
        while mes < 1:
            ano, mes = ano - 1, mes + 12
        inicio = f"{ano}-{mes:02d}"
    inicio = max(inicio, FONTES[fonte]["inicio"])
    return meses_entre(inicio, fim)


def url_do_mes(fonte, mes):
    cfg = FONTES[fonte]
    ano, m = map(int, mes.split("-"))
    return f"{BASE}/{cfg['pasta']}/{cfg['arquivo'].format(ano=ano, mes=m)}"


def _pedido(url, metodo="GET"):
    return urllib.request.Request(url, method=metodo, headers={"User-Agent": AGENTE})


def cabecalho(url):
    """ETag, data e tamanho do arquivo no S3, ou None se o mês ainda não foi publicado."""
    try:
        with urllib.request.urlopen(_pedido(url, "HEAD"), timeout=30) as resp:
            return {
                "etag": resp.headers["ETag"].strip('"'),
                "modificado_em": datetime.strptime(resp.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S %Z")
                .replace(tzinfo=timezone.utc),
                "bytes": int(resp.headers["Content-Length"]),
            }
    except urllib.error.HTTPError as erro:
        if erro.code in (403, 404):  # o bucket responde 403 ou 404 para arquivo que não existe
            return None
        raise


def baixar(url, destino, tentativas=3):
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(destino.suffix + ".part")
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(_pedido(url), timeout=120) as resp, open(parcial, "wb") as f:
                while bloco := resp.read(1 << 16):
                    f.write(bloco)
            parcial.replace(destino)
            return
        except Exception:
            if n == tentativas - 1:
                raise
            time.sleep(5 * (n + 1))


def _tipo_postgres(tipo_arrow):
    for teste, nome in TIPOS:
        if teste(tipo_arrow):
            return nome
    raise TypeError(f"tipo sem correspondência no Postgres: {tipo_arrow}")


def preparar_tabelas(cur, fonte, esquema):
    """Cria raw.<fonte> e raw._cargas se faltarem e acrescenta colunas novas que o ONS publicar."""
    cur.execute("create schema if not exists raw")
    cur.execute("""
        create table if not exists raw._cargas (
            fonte text not null,
            arquivo text not null,
            mes text not null,
            etag text not null,
            modificado_em timestamptz not null,
            bytes bigint not null,
            linhas bigint not null,
            carregado_em timestamptz not null default now(),
            primary key (fonte, arquivo)
        )""")
    colunas = ", ".join(f'"{c.name}" {_tipo_postgres(c.type)}' for c in esquema)
    cur.execute(f"create table if not exists raw.{fonte} ({colunas}, _arquivo text not null, "
                "_carregado_em timestamptz not null default now())")
    cur.execute("select column_name from information_schema.columns where table_schema = 'raw' and table_name = %s",
                (fonte,))
    existentes = {linha[0] for linha in cur.fetchall()}
    for c in esquema:
        if c.name not in existentes:
            cur.execute(f'alter table raw.{fonte} add column "{c.name}" {_tipo_postgres(c.type)}')
    cur.execute(f"create index if not exists {fonte}_arquivo on raw.{fonte} (_arquivo)")
    # o dbt lê a fonte em lotes mensais filtrando pelo instante
    cur.execute(f"create index if not exists {fonte}_instante on raw.{fonte} (din_instante)")


def copiar_csv(cur, sql, buffer):
    """COPY ... FROM STDIN nos dois drivers: o provider do Postgres usa psycopg 3 quando ele está instalado."""
    if hasattr(cur, "copy_expert"):  # psycopg2
        cur.copy_expert(sql, buffer)
        return
    with cur.copy(sql) as copia:  # psycopg 3
        while bloco := buffer.read(1 << 20):
            copia.write(bloco)


def gravar_tabela(conn, fonte, tabela, arquivo, controle=None):
    """Troca as linhas de um arquivo em raw.<fonte> numa transação.

    `controle`, se vier, é gravado em raw._cargas na mesma transação (mes, etag, modificado_em, bytes).
    Devolve quantas linhas saíram. O CI usa esta função para carregar a amostra de teste.
    """
    tabela = tabela.rename_columns([c.lower() for c in tabela.column_names])
    esquema_fonte = tabela.schema
    tabela = tabela.append_column("_arquivo", pa.array([arquivo] * tabela.num_rows, pa.string()))

    buffer = io.BytesIO()
    pacsv.write_csv(tabela, buffer, pacsv.WriteOptions(include_header=False))
    buffer.seek(0)
    colunas = ", ".join(f'"{c}"' for c in tabela.column_names)

    try:
        with conn.cursor() as cur:
            # download e leitura correm em paralelo; a escrita na tabela é uma de cada vez, porque o
            # create/alter de uma tarefa e o delete de outra travavam uma à outra (deadlock)
            cur.execute("select pg_advisory_xact_lock(hashtext(%s))", (f"raw.{fonte}",))
            preparar_tabelas(cur, fonte, esquema_fonte)
            cur.execute(f"delete from raw.{fonte} where _arquivo = %s", (arquivo,))
            removidas = cur.rowcount
            copiar_csv(cur, f"copy raw.{fonte} ({colunas}) from stdin with (format csv)", buffer)
            if controle:
                cur.execute("""
                    insert into raw._cargas (fonte, arquivo, mes, etag, modificado_em, bytes, linhas)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    on conflict (fonte, arquivo) do update set
                        etag = excluded.etag, modificado_em = excluded.modificado_em, bytes = excluded.bytes,
                        linhas = excluded.linhas, carregado_em = now()""",
                            (fonte, arquivo, controle["mes"], controle["etag"], controle["modificado_em"],
                             controle["bytes"], tabela.num_rows))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return removidas


def carregar_mes(conn, fonte, mes, forcar=False):
    """Carrega um mês de uma fonte. Devolve um dicionário com o que aconteceu."""
    url = url_do_mes(fonte, mes)
    arquivo = url.rsplit("/", 1)[1]
    info = cabecalho(url)
    if info is None:
        return {"fonte": fonte, "mes": mes, "situacao": "não publicado"}

    with conn.cursor() as cur:
        cur.execute("select to_regclass('raw._cargas')")
        anterior = None
        if cur.fetchone()[0]:
            cur.execute("select etag from raw._cargas where fonte = %s and arquivo = %s", (fonte, arquivo))
            linha = cur.fetchone()
            anterior = linha[0] if linha else None
    if anterior == info["etag"] and not forcar:
        return {"fonte": fonte, "mes": mes, "situacao": "sem mudança", "etag": info["etag"]}

    destino = DADOS / FONTES[fonte]["pasta"] / arquivo
    baixar(url, destino)
    tabela = pq.read_table(destino)
    removidas = gravar_tabela(conn, fonte, tabela, arquivo, controle={"mes": mes, **info})
    return {
        "fonte": fonte,
        "mes": mes,
        "situacao": "carregado" if anterior is None else "atualizado",
        "linhas": tabela.num_rows,
        "linhas_removidas": removidas,
        "etag": info["etag"],
        "modificado_em": info["modificado_em"].isoformat(),
    }
