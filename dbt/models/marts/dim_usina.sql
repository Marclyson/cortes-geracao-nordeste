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
),

-- O ONS repete nomes: parques híbridos (eólica e solar com o mesmo nome) e conjuntos homônimos.
-- O rótulo acrescenta a fonte e, se ainda repetir, o código da usina, para o painel não juntar usinas.
repeticoes as (
    select
        usina_id,
        count(*) over (partition by usina_nome) as com_mesmo_nome,
        count(*) over (partition by usina_nome, fonte) as com_mesmo_nome_e_fonte
    from atual
)

select
    atual.usina_id,
    atual.fonte,
    case atual.fonte when 'eolica' then 'Eólica' when 'solar' then 'Solar' end as fonte_nome,
    atual.usina_nome,
    case
        when repeticoes.com_mesmo_nome = 1 then atual.usina_nome
        when repeticoes.com_mesmo_nome_e_fonte = 1
            then atual.usina_nome || ' (' || case atual.fonte when 'eolica' then 'Eólica' else 'Solar' end || ')'
        else
            atual.usina_nome || ' (' || case atual.fonte when 'eolica' then 'Eólica' else 'Solar' end
            || ', ' || atual.usina_id || ')'
    end as usina_rotulo,
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
inner join repeticoes on atual.usina_id = repeticoes.usina_id
