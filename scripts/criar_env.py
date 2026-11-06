"""Cria o arquivo .env com senha do Postgres e chaves do Airflow sorteadas na hora.

O .env fica fora do Git. Se ele já existir, o script não mexe nele.
Uso: python scripts/criar_env.py
"""
import base64
import secrets
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"


def main():
    if ENV.exists():
        print(f"{ENV} já existe; nada foi alterado")
        return
    ENV.write_text(
        "POSTGRES_USER=dome\n"
        f"POSTGRES_PASSWORD={secrets.token_hex(16)}\n"
        f"AIRFLOW__CORE__FERNET_KEY={base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}\n"
        f"AIRFLOW__API_AUTH__JWT_SECRET={secrets.token_hex(32)}\n",
        encoding="utf-8",
    )
    print(f"criado {ENV}")


if __name__ == "__main__":
    main()
