"""DAG que roda o dbt depois de cada carga do ONS.

Não tem horário próprio: dispara quando um dos DAGs ons_restricao_* termina e atualiza o Asset da
sua tabela no schema raw. Primeiro confere se as fontes estão em dia (dbt source freshness), depois
roda modelos, snapshot e testes na ordem das dependências (dbt build).
"""
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

from ons.ativos import ATIVOS

DBT = "/opt/dbt/bin/dbt"
PASTA = "/opt/airflow/dbt"


@dag(
    dag_id="dbt_cortes",
    description="Modelos, snapshot e testes do dbt sobre os dados do ONS",
    schedule=ATIVOS["restricao_eolica"] | ATIVOS["restricao_solar"],
    catchup=False,
    max_active_runs=1,
    tags=["dbt"],
)
def dbt_cortes():
    frescor = BashOperator(
        task_id="source_freshness",
        bash_command=f"{DBT} source freshness",
        cwd=PASTA,
    )
    build = BashOperator(
        task_id="build",
        bash_command=f"{DBT} build",
        cwd=PASTA,
    )
    frescor >> build


dbt_cortes()
