"""Carrega a amostra de ci/amostra/ no schema raw, com a mesma função que a carga do Airflow usa.

Lê a conexão das mesmas variáveis de ambiente do perfil do dbt (DBT_HOST, DBT_PORT, DBT_DBNAME,
POSTGRES_USER, POSTGRES_PASSWORD). Usado pelo CI antes do dbt build.

Uso: python scripts/carregar_amostra.py
"""
import os
import sys
from pathlib import Path

import psycopg2
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "dags"))
from ons.carga import FONTES, gravar_tabela  # noqa: E402


def main():
    conn = psycopg2.connect(
        host=os.environ.get("DBT_HOST", "localhost"),
        port=int(os.environ.get("DBT_PORT", "5432")),
        dbname=os.environ.get("DBT_DBNAME", "dw"),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )
    try:
        for fonte in FONTES:
            arquivo = RAIZ / "ci/amostra" / f"{fonte}.parquet"
            tabela = pq.read_table(arquivo)
            gravar_tabela(conn, fonte, tabela, arquivo.name)
            print(f"{fonte}: {tabela.num_rows} linhas")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
