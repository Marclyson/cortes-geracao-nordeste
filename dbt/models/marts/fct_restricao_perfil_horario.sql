{#
  Perfil da restrição ao longo do dia: um registro por mês, fonte, estado e patamar de 30 minutos.
  Serve para ver em que horas o corte se concentra (a solar só gera de dia, a eólica tem picos à
  noite). Agregado sem a usina para ficar pequeno no Power BI. Incremental em lotes mensais, com
  a mesma janela da fato diária.
#}
{{ config(
    materialized='incremental',
    incremental_strategy='microbatch',
    event_time='mes',
    begin='2021-10-01',
    batch_size='month',
    lookback=2,
    indexes=[{'columns': ['mes']}]
) }}

select
    date_trunc('month', instante)::date as mes,
    fonte,
    uf,
    instante::time as patamar,
    extract(hour from instante)::int as hora,
    count(distinct usina_id) as usinas,
    count(*) as registros,
    count(*) filter (where limitada) as registros_limitados,
    sum(geracao_mwh) as geracao_mwh,
    sum(referencia_mwh) as referencia_mwh,
    sum(nao_realizada_mwh) as nao_realizada_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'ENE'), 0) as nao_realizada_ene_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'CNF'), 0) as nao_realizada_cnf_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'REL'), 0) as nao_realizada_rel_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'PAR'), 0) as nao_realizada_par_mwh
from {{ ref('int_restricao_semihoraria') }}
group by 1, 2, 3, 4, 5
