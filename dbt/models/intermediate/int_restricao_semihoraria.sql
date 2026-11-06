{{ config(event_time='instante') }}

-- As duas fontes juntas, um registro por usina a cada 30 minutos.
select * from {{ ref('stg_ons__restricao_eolica') }}
union all
select * from {{ ref('stg_ons__restricao_solar') }}
