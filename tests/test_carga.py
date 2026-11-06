"""Testes das funções da carga que não dependem de rede nem de banco."""
from datetime import datetime

from ons.carga import meses_da_execucao, meses_entre, url_do_mes


def test_meses_entre_atravessa_o_ano():
    assert meses_entre("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_janela_padrao_confere_o_mes_e_os_dois_anteriores():
    assert meses_da_execucao("restricao_eolica", datetime(2026, 1, 15)) == ["2025-11", "2025-12", "2026-01"]


def test_janela_nao_volta_antes_do_inicio_da_fonte():
    assert meses_da_execucao("restricao_solar", datetime(2024, 5, 1), meses_atras=6) == ["2024-04", "2024-05"]


def test_carga_historica_usa_desde():
    meses = meses_da_execucao("restricao_eolica", datetime(2026, 11, 5), desde="2021-10")
    assert meses[0] == "2021-10"
    assert meses[-1] == "2026-11"
    assert len(meses) == 62


def test_url_do_mes():
    assert url_do_mes("restricao_solar", "2026-03").endswith(
        "/restricao_coff_fotovoltaica_tm/RESTRICAO_COFF_FOTOVOLTAICA_2026_03.parquet"
    )
