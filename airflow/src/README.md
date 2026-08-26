# `airflow/src/` — code métier du pipeline orders (Python pur)

Ce dossier contient les modules métier exécutés par le DAG `orders_pipeline`
(Bronze → Silver → Gold) : `config.py`, `extract.py`, `transform.py`, `load.py`.

> [!IMPORTANT] Source de vérité = le cours
> Ce dossier est un **patch aligné sur le dépôt de cours** `cours-big-data-local-2j`
> (dossier `CODE/`). Les apprenants partent de `CODE/` et **copient ces fichiers** ici
> au TP2 — les deux versions partagent les mêmes contrats (`MinIOConfig.from_env`,
> `extract_bronze`, `transform_silver`, `aggregate_gold`, etc.).
>
> Si vous voyez une différence d'implémentation entre `CODE/` et ce dossier, **c'est
> `CODE/` qui fait foi**. Signalez-le — c'est un bug d'alignement, pas une feature.

## Contexte d'exécution

- Monté sur `/opt/airflow/src` dans les conteneurs Airflow (cf. `docker-compose.yml`).
- `PYTHONPATH=/opt/airflow` → le DAG importe via `from src.extract import ...`.
- Les modules s'importent aussi « à plat » (`from transform import ...`) quand on
  travaille ici directement (tests, exo8, notebook) — les imports internes utilisent
  cette forme.

## Tests

```bash
# depuis la racine big-data-lab-infra
pytest tests/airflow_src/ -v
```

Python pur (boto3 + stdlib), sans pandas ni Spark.
