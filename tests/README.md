# Tests

Suite pytest du code métier `airflow/src/` et du contrat des DAGs. Exécution
**hors Docker et hors Airflow** — c'est l'amorce du TP3 qui prévoit des tests
pytest sur les DAGs et le code métier.

> Outillage **mainteneur** : ce dossier n'est pas distribué dans le zip
> apprenant (`export-ignore`).

## Exécution locale

```bash
pip install -r requirements.txt   # pytest, ruff, mypy, moto
pytest -q                         # toute la suite
pytest tests/airflow_src/         # uniquement le métier
pytest -k transform               # filtre par nom
```

## Lint & types

```bash
ruff check .
ruff format --check .
mypy
```

## Contenu

```
tests/
├── conftest.py                # sys.path + vars d'env factices, staging temporaire
├── test_dag_contract.py       # chaque DAG s'importe, bon dag_id, pas de cycle
└── airflow_src/
    ├── test_config.py         # MinIOConfig lit les env vars
    ├── test_transform.py      # dédup, total_price, filtre status
    ├── test_extract.py        # pagination S3 + parse JSONL (moto)
    └── test_load.py           # agrégation Gold + écriture idempotente (moto)
```

## Ajouter des tests

- `extract.py` / `load.py` touchent MinIO : mocker le client S3 avec
  [`moto`](https://github.com/getmoto/moto) — `@mock_aws` +
  `boto3.client("s3", endpoint_url=…)` (voir `test_extract.py`).
- Pour valider la structure des DAGs sans Airflow, voir `test_dag_contract.py`
  (AST, sans import d'Airflow).
