# Tests

Squelette de tests pour `airflow/src/` (métier testable **hors Docker et hors
Airflow**). C'est l'amorce du **TP3 N3** qui prévoit des tests pytest sur les
DAGs et le code métier.

## Exécution locale

```bash
pip install -r requirements.txt   # installe aussi pytest + ruff
pytest                            # lance tous les tests
pytest tests/airflow_src/         # uniquement le métier
pytest -k transform               # filtre par nom
```

## Lint

```bash
ruff check .
ruff check --fix .                # corrige les erreurs auto (imports, etc.)
```

## Contenu

```
tests/
├── conftest.py                # fixtures : vars d'env factices, staging temporaire
└── airflow_src/
    ├── test_config.py         # MinIOConfig lit les env vars + s3_url()
    └── test_transform.py      # transform_orders : dédup, total_price, filtre status
```

## Ajouter des tests

- Pour tester `extract.py` / `load.py` (qui touchent MinIO), mocker le client
  boto3 avec [`moto`](https://github.com/getmoto/moto) (non inclus ici pour
  garder les deps légères) : `@mock_aws` + `boto3.client("s3", endpoint_url=…)`.
- Pour valider les DAGs (import, structure, cycles), voir
  `airflow.utils.dag_test` et `pytest-airflow`.
