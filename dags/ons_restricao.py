"""DAGs que trazem do ONS os cortes de geração das usinas eólicas e solares para o schema raw.

Um DAG por fonte (ons_restricao_eolica, ons_restricao_solar). Cada execução confere o mês corrente e
os dois anteriores, porque o ONS regrava meses já publicados. Só baixa o arquivo cujo ETag mudou.

Para a carga histórica, dispare o DAG à mão com o parâmetro `desde` (por exemplo, 2021-10).
Para baixar de novo mesmo sem mudança no ETag, marque `forcar`.
"""
from datetime import timedelta

import pendulum
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import Param, dag, get_current_context, task

from ons.ativos import ATIVOS
from ons.carga import FONTES, carregar_mes, meses_da_execucao

RIO = pendulum.timezone("America/Sao_Paulo")


def criar_dag(fonte):
    @dag(
        dag_id=f"ons_{fonte}",
        description=FONTES[fonte]["descricao"],
        # o ONS publica por volta das 12h e das 19h; meia hora de folga
        schedule="30 12,19 * * *",
        start_date=pendulum.datetime(2026, 11, 1, tz=RIO),
        catchup=False,
        max_active_runs=1,
        tags=["ons", "raw"],
        default_args={"retries": 3, "retry_delay": timedelta(minutes=5)},
        params={
            "meses_atras": Param(2, type="integer", minimum=0, maximum=60,
                                 description="Quantos meses antes do atual conferir"),
            "desde": Param(None, type=["null", "string"], pattern=r"^\d{4}-\d{2}$",
                           description="Carga histórica: conferir todos os meses desde AAAA-MM"),
            "forcar": Param(False, type="boolean", description="Baixar de novo mesmo sem mudança no ETag"),
        },
    )
    def ons_restricao():
        @task
        def listar_meses():
            ctx = get_current_context()
            # execuções manuais no Airflow 3 podem vir sem logical_date; run_after sempre existe
            referencia = pendulum.instance(ctx.get("logical_date") or ctx["dag_run"].run_after).in_timezone(RIO)
            p = ctx["params"]
            return meses_da_execucao(fonte, referencia, p["meses_atras"], p["desde"])

        @task(max_active_tis_per_dagrun=4)
        def carregar(mes):
            ctx = get_current_context()
            conn = PostgresHook(postgres_conn_id="dw").get_conn()
            try:
                resultado = carregar_mes(conn, fonte, mes, forcar=ctx["params"]["forcar"])
            finally:
                conn.close()
            print(resultado)
            return resultado

        # ao terminar, avisa o DAG do dbt que a tabela raw desta fonte foi conferida
        @task(outlets=[ATIVOS[fonte]])
        def resumir(resultados):
            contagem = {}
            for r in resultados:
                contagem[r["situacao"]] = contagem.get(r["situacao"], 0) + 1
                if r["situacao"] in ("carregado", "atualizado"):
                    print(f"{r['mes']}: {r['situacao']}, {r['linhas']} linhas (antes {r['linhas_removidas']})")
            print(contagem)
            return contagem

        resumir(carregar.expand(mes=listar_meses()))

    return ons_restricao()


for _fonte in FONTES:
    criar_dag(_fonte)
