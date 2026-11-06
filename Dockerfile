# Imagem do Airflow com o dbt num ambiente Python separado, para as dependências de um não
# atrapalharem as do outro. O Airflow chama /opt/dbt/bin/dbt.
FROM apache/airflow:3.3.2-python3.12

USER root
RUN mkdir /opt/dbt && chown airflow:0 /opt/dbt
USER airflow

RUN python -m venv /opt/dbt \
 && /opt/dbt/bin/pip install --no-cache-dir dbt-core==1.12.6 dbt-postgres==1.11.0
