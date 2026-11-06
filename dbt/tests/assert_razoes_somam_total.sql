-- A geração não realizada separada por razão precisa somar o total do dia.
select
    usina_id,
    dia,
    nao_realizada_mwh,
    nao_realizada_ene_mwh + nao_realizada_cnf_mwh + nao_realizada_rel_mwh
    + nao_realizada_par_mwh + nao_realizada_sem_razao_mwh as soma_razoes
from {{ ref('fct_restricao_usina_dia') }}
where abs(nao_realizada_mwh - (
    nao_realizada_ene_mwh + nao_realizada_cnf_mwh + nao_realizada_rel_mwh
    + nao_realizada_par_mwh + nao_realizada_sem_razao_mwh
)) > 0.001
