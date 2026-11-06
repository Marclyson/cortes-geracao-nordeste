"""Gera a amostra pequena de dados do ONS que o CI usa para rodar o dbt.

Lê os Parquet de outubro de 2026 já baixados pela carga (dados/ons/...) e guarda em ci/amostra/ os
três primeiros dias de algumas usinas: as que mais tiveram restrição em cada razão, algumas sem
restrição e pelo menos uma com código CEG. Os dados são do ONS, licença CC BY 4.0.

Uso: python scripts/gerar_amostra.py
"""
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = {
    "restricao_eolica": RAIZ / "dados/ons/restricao_coff_eolica_tm/RESTRICAO_COFF_EOLICA_2026_10.parquet",
    "restricao_solar": RAIZ / "dados/ons/restricao_coff_fotovoltaica_tm/RESTRICAO_COFF_FOTOVOLTAICA_2026_10.parquet",
}
DESTINO = RAIZ / "ci/amostra"
INICIO, FIM = datetime(2026, 10, 1), datetime(2026, 10, 4)


def escolher_usinas(tabela, por_razao=2, sem_restricao=2):
    linhas = tabela.select(["id_ons", "ceg", "cod_razaorestricao", "val_geracaonaorealizadaapurada"]).to_pylist()
    perda = {}
    for linha in linhas:
        razao = linha["cod_razaorestricao"]
        if razao:
            chave = (razao, linha["id_ons"])
            perda[chave] = perda.get(chave, 0) + (linha["val_geracaonaorealizadaapurada"] or 0)
    escolhidas = []
    for razao in sorted({r for r, _ in perda}):
        maiores = sorted(((v, u) for (r, u), v in perda.items() if r == razao), reverse=True)
        escolhidas += [u for _, u in maiores if u not in escolhidas][:por_razao]
    com_restricao = {u for _, u in perda}
    sem = sorted({linha["id_ons"] for linha in linhas} - com_restricao)
    escolhidas += sem[:sem_restricao]
    com_ceg = sorted({linha["id_ons"] for linha in linhas if linha["ceg"] not in (None, "-")})
    if com_ceg and not set(com_ceg) & set(escolhidas):
        escolhidas.append(com_ceg[0])
    return escolhidas


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for fonte, origem in ORIGEM.items():
        tabela = pq.read_table(origem)
        periodo = pc.and_(pc.greater_equal(tabela["din_instante"], INICIO), pc.less(tabela["din_instante"], FIM))
        tabela = tabela.filter(periodo)
        usinas = escolher_usinas(tabela)
        amostra = tabela.filter(pc.is_in(tabela["id_ons"], value_set=pa.array(usinas)))
        destino = DESTINO / f"{fonte}.parquet"
        pq.write_table(amostra, destino, compression="zstd")
        print(f"{fonte}: {len(usinas)} usinas, {amostra.num_rows} linhas, {destino.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
