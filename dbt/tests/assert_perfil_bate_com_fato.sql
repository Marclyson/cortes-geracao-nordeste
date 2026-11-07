-- O perfil horário, somado por mês, precisa bater com a fato diária.
with perfil as (
    select
        mes,
        sum(nao_realizada_mwh) as nao_realizada_mwh
    from {{ ref('fct_restricao_perfil_horario') }}
    group by mes
),

fato as (
    select
        date_trunc('month', dia)::date as mes,
        sum(nao_realizada_mwh) as nao_realizada_mwh
    from {{ ref('fct_restricao_usina_dia') }}
    group by date_trunc('month', dia)::date
)

select
    fato.mes,
    fato.nao_realizada_mwh as fato_mwh,
    perfil.nao_realizada_mwh as perfil_mwh
from fato
full outer join perfil on fato.mes = perfil.mes
where abs(coalesce(fato.nao_realizada_mwh, 0) - coalesce(perfil.nao_realizada_mwh, 0)) > 0.01
