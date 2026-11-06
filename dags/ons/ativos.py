"""Assets do Airflow que representam as tabelas do schema raw.

Os DAGs de carga atualizam o Asset da sua tabela ao terminar, e o DAG do dbt é agendado por eles.
"""
from airflow.sdk import Asset

from ons.carga import FONTES

ATIVOS = {fonte: Asset(f"postgres://postgres:5432/dw/raw/{fonte}") for fonte in FONTES}
