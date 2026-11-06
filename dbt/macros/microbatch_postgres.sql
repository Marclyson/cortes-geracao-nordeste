{#
  Microbatch no Postgres que troca o lote inteiro.

  O dbt-postgres 1.11 implementa o microbatch com merge pela unique_key. Com merge, uma linha que
  sumiu da fonte (uma usina que o ONS retirou ao revisar um mês) continua no destino. Aqui o lote é
  tratado como uma janela de tempo: apaga tudo de event_time_start até event_time_end e insere o que
  o lote calculou, do mesmo jeito que os adaptadores de Snowflake e BigQuery fazem.
#}
{% macro postgres__get_incremental_microbatch_sql(arg_dict) %}
    {%- set alvo = arg_dict["target_relation"] -%}
    {%- set lote = arg_dict["temp_relation"] -%}
    {%- set colunas = get_quoted_csv(arg_dict["dest_columns"] | map(attribute="name")) -%}
    {%- set coluna_tempo = model.config.event_time -%}
    {%- set filtros = [] if arg_dict.get("incremental_predicates") is none else arg_dict.get("incremental_predicates") -%}

    {%- if model.batch and model.batch.event_time_start -%}
        {%- do filtros.append(coluna_tempo ~ " >= '" ~ model.batch.event_time_start.strftime('%Y-%m-%d %H:%M:%S') ~ "'::timestamp") -%}
    {%- endif -%}
    {%- if model.batch and model.batch.event_time_end -%}
        {%- do filtros.append(coluna_tempo ~ " < '" ~ model.batch.event_time_end.strftime('%Y-%m-%d %H:%M:%S') ~ "'::timestamp") -%}
    {%- endif -%}
    {%- if not filtros -%}
        {{ exceptions.raise_compiler_error("microbatch sem janela de tempo: nada a apagar com segurança") }}
    {%- endif -%}

    delete from {{ alvo }}
    where {{ filtros | join(" and ") }};

    insert into {{ alvo }} ({{ colunas }})
    select {{ colunas }} from {{ lote }}
{% endmacro %}
