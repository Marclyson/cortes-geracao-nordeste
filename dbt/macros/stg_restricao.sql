{#
  Staging comum às duas fontes de restrição do ONS (eólica e solar), que têm as mesmas colunas.
  Os valores de energia vêm em MW médios de cada patamar de 30 minutos. Para ter MWh, multiplica
  por meia hora. A geração não realizada (GNRa) vem nula quando não houve limitação; aqui vira zero.
#}
{% macro stg_restricao(tabela, fonte) %}
select
    '{{ fonte }}'::text                           as fonte,
    id_ons                                        as usina_id,
    nom_usina                                     as usina_nome,
    nullif(trim(ceg), '-')                        as ceg,
    id_subsistema                                 as subsistema_id,
    nom_subsistema                                as subsistema,
    id_estado                                     as uf,
    nom_estado                                    as estado,
    id_pontoconexao                               as ponto_conexao_id,
    nom_pontoconexao                              as ponto_conexao,
    nom_agenteoperador                            as agente_operador,
    din_instante                                  as instante,
    din_instante::date                            as dia,
    val_geracao * 0.5                             as geracao_mwh,
    val_disponibilidade * 0.5                     as disponibilidade_mwh,
    val_geracaoreferencia * 0.5                   as referencia_mwh,
    val_geracaoreferenciafinal * 0.5              as referencia_final_mwh,
    val_geracaolimitada                           as limite_mw,
    val_geracaolimitada is not null               as limitada,
    coalesce(val_geracaonaorealizadaapurada, 0) * 0.5 as nao_realizada_mwh,
    cod_razaorestricao                            as razao,
    cod_origemrestricao                           as origem,
    nullif(trim(dsc_restricao), '')               as descricao_restricao,
    num_minutos_restricao::int                    as minutos_restricao,
    num_minutos_rel::int                          as minutos_rel,
    num_minutos_cnf::int                          as minutos_cnf,
    num_minutos_ene::int                          as minutos_ene,
    _arquivo                                      as arquivo,
    _carregado_em                                 as carregado_em
from {{ source('ons', tabela) }}
{% endmacro %}
