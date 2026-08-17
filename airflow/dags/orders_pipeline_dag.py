"""
DAG orders_pipeline — orchestration du pipeline commandes Bronze → Silver → Gold.

Le code métier vit dans airflow/src/ (extract, transform, load) et reste testable
hors Airflow. Ce DAG n'est qu'une fine couche d'orchestration : il appelle les
modules src/ et ne duplique aucune logique.

Les tâches communiquent via des fichiers Parquet de staging (volume ./data monté
dans le conteneur) plutôt que par XCom — adapté aux volumes pandas.

Idempotence : load écrit une partition ds=YYYY-MM-DD qui écrase la précédente,
donc rejouer le DAG pour la même date ne crée jamais de doublon.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# --- Rendre les modules ETL importables --------------------------------------
# ./airflow/src est monté dans le conteneur sous /opt/airflow/src (voir docker-compose).
sys.path.insert(0, "/opt/airflow")

from src import extract, transform, load  # noqa: E402

logger = logging.getLogger(__name__)


# =============================================================================
# Fonctions de tâches — wrappers minces autour des modules src/
# =============================================================================
def _extract(ds, **_):
    """Bronze : lit les JSON raw/orders du jour depuis MinIO → staging Parquet."""
    extract.extract_orders(ds)


def _transform(ds, **_):
    """Silver : typage, dédup event_id, calcul total_price → staging Parquet."""
    transform.transform_orders(ds)


def _load(ds, **_):
    """Gold : agrège CA par jour+produit → écriture idempotente dans MinIO."""
    metrics = load.load_gold(ds)
    logger.info("Métriques Gold pour %s : %s", ds, metrics)


# =============================================================================
# Définition du DAG
# =============================================================================
default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="orders_pipeline",
    description="Pipeline commandes : Bronze → Silver → Gold (orchestration de src/)",
    start_date=datetime(2026, 3, 1),
    schedule="0 6 * * *",
    catchup=False,
    default_args=default_args,
    tags=["orders", "data-engineering"],
) as dag:

    task_bronze = PythonOperator(task_id="ingest_bronze",   python_callable=_extract)
    task_silver = PythonOperator(task_id="transform_silver", python_callable=_transform)
    task_gold   = PythonOperator(task_id="aggregate_gold",   python_callable=_load)

    task_bronze >> task_silver >> task_gold
