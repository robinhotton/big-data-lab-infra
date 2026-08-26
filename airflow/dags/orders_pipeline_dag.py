"""orders_pipeline_dag.py — DAG Airflow : pipeline commandes Bronze -> Silver -> Gold.

Version *lab* du DAG `orders_pipeline` du cours (cours-big-data-local-2j, TP2). Elle
orchestre les modules metier alignes dans `airflow/src/` (`config`, `extract`,
`transform`, `load`), en Python pur (boto3 + stdlib), sans pandas ni Spark.

Le code metier vit dans `airflow/src/` et reste testable hors Airflow. Ce DAG n'est
qu'une fine couche d'orchestration : il appelle `src/` et ne duplique aucune logique.

Passage de donnees entre taches : via **XCom** (200 events/jour, volume leger — pas
de staging Parquet). Un DAG qui stocke sa donnee intermediaire dans une variable
globale (`_BRONZE`) NE FONCTIONNE PAS avec LocalExecutor, car chaque tache tourne
dans un processus separe : la globale n'est pas partagee. D'ou XCom.

Les invalides de Silver partent en `quarantine/`, les agregats Gold en
`curated/ca_by_status_{ds}.json` (ecriture idempotente, cle datee -> re-run ecrase).

Deploiement : `big-data-lab-infra/airflow/dags/` (monte sur `/opt/airflow/dags`).
Modules metier dans `airflow/src/` (monte `/opt/airflow/src`, PYTHONPATH inclut
`/opt/airflow` et `/opt/airflow/src` — cf. docker-compose).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# Rendre les modules metier importables : ./airflow/src est monte sur /opt/airflow/src.
sys.path.insert(0, "/opt/airflow")

from src.extract import extract_bronze  # noqa: E402
from src.transform import transform_silver  # noqa: E402
from src.load import aggregate_gold, write_json_to_minio, write_quarantine  # noqa: E402


def _ds_from_context(context) -> str:
    """Date logique : `conf["ds"]` du trigger si fournie, sinon `context["ds"]`."""
    return (context.get("dag_run") and context["dag_run"].conf.get("ds")) or context["ds"]


def task_extract_bronze(**context) -> list[dict]:
    """Bronze : lit les JSON orders du jour. Retourne les events (-> XCom)."""
    ds = _ds_from_context(context)
    events = extract_bronze(ds)
    print(f"Bronze : {len(events)} events pour {ds}")
    return events


def task_transform_silver(events: list[dict], **context) -> list[dict]:
    """Silver : valide, deduplique, ajoute total_price. Invalides -> quarantine.

    Retourne les events valides (-> XCom, consomme par load_gold).
    """
    ds = _ds_from_context(context)
    valid, invalid = transform_silver(list(events))
    write_quarantine(invalid, ds)
    print(f"Silver : {len(valid)} valides, {len(invalid)} -> quarantine")
    return valid


def task_load_gold(valid_events: list[dict], **context) -> dict:
    """Gold : agrege le CA par status et ecrit en curated/ (idempotent)."""
    ds = _ds_from_context(context)
    gold = aggregate_gold(list(valid_events))
    write_json_to_minio(f"curated/ca_by_status_{ds}.json", gold)
    print(f"Gold : CA par status pour {ds} = {gold['ca_by_status']}")
    return gold


default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="orders_pipeline",
    description="Pipeline commandes : Bronze -> Silver -> Gold (Python pur, src/)",
    schedule="0 6 * * *",             # cron : tous les jours a 6h
    start_date=datetime(2026, 3, 1),  # toujours datetime(), jamais days_ago()
    catchup=False,                    # pas de backfill automatique
    default_args=default_args,
    tags=["orders", "bronze-silver-gold", "pure-python"],
) as dag:

    t_bronze = PythonOperator(task_id="extract_bronze",
                              python_callable=task_extract_bronze)
    t_silver = PythonOperator(task_id="transform_silver",
                              python_callable=task_transform_silver,
                              op_args=[t_bronze.output])  # XComArg des events Bronze
    t_gold = PythonOperator(task_id="load_gold",
                            python_callable=task_load_gold,
                            op_args=[t_silver.output])    # XComArg des events Silver

    t_bronze >> t_silver >> t_gold
