-- A geração não realizada separada por origem (local, sistêmica, sem origem) precisa somar o total do dia.
select
    usina_id,
    dia,
    nao_realizada_mwh
from {{ ref('fct_restricao_usina_dia') }}
where abs(nao_realizada_mwh - (
    nao_realizada_loc_mwh + nao_realizada_sis_mwh + nao_realizada_sem_origem_mwh
)) > 0.001
