-- A soma mensal da fato precisa bater com a da staging. Pega diferença deixada pela carga
-- incremental, como um mês que o ONS revisou fora da janela de reprocessamento.
with staging as (
    select fonte, date_trunc('month', dia) as mes, sum(geracao_mwh) as geracao, sum(nao_realizada_mwh) as nao_realizada
    from {{ ref('int_restricao_semihoraria') }}
    group by 1, 2
),

fato as (
    select fonte, date_trunc('month', dia) as mes, sum(geracao_mwh) as geracao, sum(nao_realizada_mwh) as nao_realizada
    from {{ ref('fct_restricao_usina_dia') }}
    group by 1, 2
)

select coalesce(s.fonte, f.fonte) as fonte, coalesce(s.mes, f.mes) as mes,
       s.geracao as geracao_staging, f.geracao as geracao_fato,
       s.nao_realizada as nao_realizada_staging, f.nao_realizada as nao_realizada_fato
from staging s
full join fato f on f.fonte = s.fonte and f.mes = s.mes
where s.mes is null or f.mes is null
   or abs(s.geracao - f.geracao) > 0.01
   or abs(s.nao_realizada - f.nao_realizada) > 0.01
