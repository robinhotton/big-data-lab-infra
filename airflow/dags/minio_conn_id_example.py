"""
DAG minio_conn_id_example — illustre l'accès à MinIO via une **connexion Airflow**
(conn_id) plutôt que via un client boto3 direct.

Pourquoi ce DAG ?
  - `orders_pipeline` crée son client boto3 dans airflow/src/config.py (approche
    "boto3 direct", légère, sans dépendance à un provider Airflow).
  - Ce DAG montre l'autre approche : un `S3Hook(conn_id="minio_default")` qui
    s'appuie sur une connexion déclarée dans Airflow (UI → Admin → Connections,
    ou variable d'environnement `AIRFLOW_CONN_MINIO_DEFAULT`).

La connexion `minio_default` est créée automatiquement au démarrage par la
variable `AIRFLOW_CONN_MINIO_DEFAULT` définie dans docker-compose.yml — aucune
configuration manuelle dans l'UI n'est nécessaire.

Ce DAG est volontairement pédagogique et n'a pas de logique métier : il liste,
compte et vérifie la présence des datasets dans le bucket `data-lake`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

logger = logging.getLogger(__name__)

# conn_id déclaré dans docker-compose (AIRFLOW_CONN_MINIO_DEFAULT)
CONN_ID = "minio_default"
BUCKET = "data-lake"


# =============================================================================
# Fonctions de tâches
# =============================================================================
def _list_datasets(**_):
    """Liste les clés sous le préfixe `raw/` et compte les objets par dataset."""
    hook = S3Hook(CONN_ID)
    keys = hook.list_keys(bucket_name=BUCKET, prefix="raw/")
    if keys is None:
        keys = []
    logger.info("Trouvé %d objet(s) sous raw/ dans %s", len(keys), BUCKET)

    # Regroupement par dataset (raw/<dataset>/...)
    by_dataset: dict[str, int] = {}
    for key in keys:
        parts = key.split("/")
        if len(parts) >= 2:
            dataset = parts[1]  # ex. "sales", "taxi", "orders", "weather"
            by_dataset[dataset] = by_dataset.get(dataset, 0) + 1

    for dataset, count in sorted(by_dataset.items()):
        logger.info("  • %s : %d objet(s)", dataset, count)

    return {"total": len(keys), "by_dataset": by_dataset}


def _check_orders(**_):
    """Vérifie qu'au moins un fichier orders du TP3 est présent."""
    hook = S3Hook(CONN_ID)
    exists = hook.check_for_prefix(
        bucket_name=BUCKET,
        prefix="raw/orders/2026/03/",
    )
    if not exists:
        raise ValueError(
            "Aucun dataset orders trouvé sous raw/orders/2026/03/ — "
            "lancez `docker compose up -d` (profile datasets) pour charger les données."
        )
    logger.info("✓ Dataset orders (TP3) présent.")
    return {"orders_present": True}


def _summary(ti, **_):
    """Résume les résultats des tâches précédentes (via XCom ici — volume léger)."""
    list_result = ti.xcom_pull(task_ids="list_datasets")
    logger.info("Résumé : %s", list_result)
    logger.info("Vérification orders OK — vous pouvez déclencher orders_pipeline.")


# =============================================================================
# Définition du DAG
# =============================================================================
default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="minio_conn_id_example",
    description="Exemple : accès MinIO via Airflow Connection (S3Hook + conn_id)",
    start_date=datetime(2026, 3, 1),
    schedule=None,  # déclenchement manuel uniquement (DAG d'exemple)
    catchup=False,
    default_args=default_args,
    tags=["exemple", "minio", "conn_id"],
) as dag:

    task_list = PythonOperator(task_id="list_datasets",  python_callable=_list_datasets)
    task_check = PythonOperator(task_id="check_orders",  python_callable=_check_orders)
    task_sum   = PythonOperator(task_id="summary",       python_callable=_summary)

    task_list >> task_check >> task_sum
