{#
  Um registro por usina e dia. Incremental em lotes mensais (microbatch): cada execução refaz o mês
  corrente e os dois anteriores, a mesma janela que o Airflow confere no ONS. O lote inteiro é
  apagado e regravado, então uma linha que o ONS retirar numa revisão também sai daqui.
#}
{{ config(
    materialized='incremental',
    incremental_strategy='microbatch',
    event_time='dia',
    begin='2021-10-01',
    batch_size='month',
    lookback=2,
    indexes=[{'columns': ['usina_id', 'dia'], 'unique': true}, {'columns': ['dia']}]
) }}

select
    usina_id,
    dia,
    min(fonte)                                                          as fonte,
    mode() within group (order by agente_operador)                      as agente_operador,
    min(uf)                                                             as uf,
    min(subsistema_id)                                                  as subsistema_id,
    count(*)                                                            as patamares,
    count(*) filter (where limitada)                                    as patamares_limitados,
    sum(least(greatest(minutos_restricao, 0), 30)) / 60.0               as horas_restricao,
    count(*) filter (where minutos_restricao not between 0 and 30)      as patamares_minutos_invalidos,
    sum(geracao_mwh)                                                    as geracao_mwh,
    sum(referencia_mwh)                                                 as referencia_mwh,
    sum(nao_realizada_mwh)                                              as nao_realizada_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'ENE'), 0)    as nao_realizada_ene_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'CNF'), 0)    as nao_realizada_cnf_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'REL'), 0)    as nao_realizada_rel_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao = 'PAR'), 0)    as nao_realizada_par_mwh,
    coalesce(sum(nao_realizada_mwh) filter (where razao is null), 0)    as nao_realizada_sem_razao_mwh
from {{ ref('int_restricao_semihoraria') }}
group by usina_id, dia
