# Cortes de geração eólica e solar no Nordeste

Projeto de estudo de engenharia de dados com dados abertos do ONS (Operador Nacional do Sistema
Elétrico). Desde 2023 o ONS limita a geração de usinas eólicas e solares, principalmente no Nordeste,
por falta de capacidade de transmissão, por segurança da rede ou por falta de consumo. O setor chama
isso de *constrained-off* ou *curtailment*. O projeto mede quanta energia deixou de ser gerada, onde e por qual motivo.

Em andamento. Feito até aqui: a carga dos dados brutos com Airflow. Faltam a modelagem com dbt, a
integração contínua no GitHub Actions e o painel em Power BI.

## Dados

| Fonte | Desde | Granularidade |
|---|---|---|
| [Restrição de operação das usinas eólicas](https://dados.ons.org.br/dataset/restricao_coff_eolica_usi) | out/2021 | usina, 30 min |
| [Restrição de operação das usinas fotovoltaicas](https://dados.ons.org.br/dataset/restricao_coff_fotovoltaica) | abr/2024 | usina, 30 min |

Licença CC BY 4.0. O ONS publica um arquivo Parquet por mês e atualiza o mês corrente por volta das
12h e das 19h. Meses anteriores também são regravados: o arquivo de outubro de 2026 mudou em 5 de novembro.

## Como a carga funciona

Cada fonte tem um DAG no Airflow (`ons_restricao_eolica` e `ons_restricao_solar`) que roda às 12h30
e às 19h30. A execução confere o mês corrente e os dois anteriores e compara o ETag de cada arquivo
no S3 com o da última carga, guardado em `raw._cargas`. Quando o ETag muda, baixa o arquivo e troca
as linhas daquele mês numa transação. Rodar a mesma execução duas vezes deixa o banco igual.

Parâmetros ao disparar à mão:

- `desde`: carga histórica a partir de um mês, por exemplo `2021-10`
- `meses_atras`: quantos meses antes do atual conferir (padrão 2)
- `forcar`: baixa de novo mesmo sem mudança no ETag

Se o ONS acrescentar uma coluna, a carga cria a coluna na tabela `raw` antes de inserir.

## Como rodar

Precisa do Docker com Docker Compose e do Python 3 (só para gerar o `.env`).

```bash
python scripts/criar_env.py
docker compose up -d
```

O `criar_env.py` sorteia a senha do Postgres e as chaves do Airflow e grava tudo no `.env`, que fica
fora do Git. O Airflow abre em http://localhost:8080, sem login, porque escuta só na própria máquina.
O Postgres atende em `localhost:5433`, banco `dw`, com usuário e senha do `.env`.

Os DAGs começam pausados. Para a carga histórica da eólica, ative o DAG e dispare com `{"desde": "2021-10"}`.

Para parar os containers sem perder os dados:

```bash
docker compose stop
```

## Estrutura

```
dags/ons_restricao.py   DAGs, um por fonte
dags/ons/carga.py       download, comparação de ETag e carga no Postgres
docker-compose.yml      Airflow 3 (LocalExecutor) e Postgres 17
postgres/init.sql       cria os bancos airflow e dw
scripts/criar_env.py    gera o .env
```

## Licença

Código sob licença MIT. Dados do ONS sob CC BY 4.0.
