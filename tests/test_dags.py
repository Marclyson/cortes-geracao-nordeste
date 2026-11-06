"""Confere se todos os DAGs importam sem erro e com a estrutura esperada. Precisa do Airflow instalado."""
from pathlib import Path

import pytest

pytest.importorskip("airflow")

from airflow.dag_processing.dagbag import DagBag  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(PASTA))


def test_sem_erro_de_importacao(dagbag):
    assert dagbag.import_errors == {}


def test_dags_esperados(dagbag):
    assert set(dagbag.dag_ids) == {"ons_restricao_eolica", "ons_restricao_solar", "dbt_cortes"}


def test_cargas_avisam_o_dbt(dagbag):
    for fonte in ("eolica", "solar"):
        resumir = dagbag.dags[f"ons_restricao_{fonte}"].get_task("resumir")
        assert [a.uri for a in resumir.outlets] == [f"postgres://postgres:5432/dw/raw/restricao_{fonte}"]


def test_dbt_confere_frescor_antes_do_build(dagbag):
    dag = dagbag.dags["dbt_cortes"]
    assert dag.get_task("build").upstream_task_ids == {"source_freshness"}
