-- Um registro por dia, do primeiro ao último mês com dados. O Power BI usa como tabela de datas.
with limites as (
    select
        date_trunc('month', min(dia))::date as inicio,
        (date_trunc('month', max(dia)) + interval '1 month - 1 day')::date as fim
    from {{ ref('fct_restricao_usina_dia') }}
),

dias as (
    select generate_series(limites.inicio, limites.fim, interval '1 day')::date as dia
    from limites
)

select
    dia,
    extract(year from dia)::int as ano,
    extract(month from dia)::int as mes_numero,
    date_trunc('month', dia)::date as mes,
    to_char(dia, 'YYYY-MM') as ano_mes,
    (array['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'])[
        extract(month from dia)::int
    ] || '/' || to_char(dia, 'YY') as mes_rotulo
from dias
