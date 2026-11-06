import sys
from pathlib import Path

# os DAGs importam o pacote ons a partir da pasta dags, como o Airflow faz
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "dags"))
