{# Usa o nome do schema configurado (staging, intermediate, marts, snapshots) sem o prefixo do
   schema do perfil, que o dbt põe por padrão. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
