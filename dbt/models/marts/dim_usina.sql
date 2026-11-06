-- Versão atual do cadastro de cada usina, com o período em que ela aparece nos dados.
with atual as (
    select * from {{ ref('snap_usina') }}
    where dbt_valid_to is null
),

periodo as (
    select
        usina_id,
        min(dia) as primeiro_dia,
        max(dia) as ultimo_dia
    from {{ ref('fct_restricao_usina_dia') }}
    group by usina_id
)

select
    atual.usina_id,
    atual.fonte,
    atual.usina_nome,
    atual.ceg,
    atual.ceg is null as conjunto_de_usinas,
    atual.uf,
    atual.estado,
    atual.subsistema_id,
    atual.subsistema,
    atual.ponto_conexao_id,
    atual.ponto_conexao,
    atual.agente_operador,
    periodo.primeiro_dia,
    periodo.ultimo_dia,
    atual.dbt_valid_from as cadastro_desde
from atual
left join periodo on atual.usina_id = periodo.usina_id
