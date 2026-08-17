"""
DAG exemple — pipeline Data Lake simplifié
Simule les étapes Raw → Cleansed → Curated sans dépendance externe.
"""
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "formation",
    "retries": 0,
}


def extract():
    print("[ EXTRACT ] Lecture des fichiers bruts depuis raw/")
    print("  -> 3 fichiers CSV détectés")
    return {"nb_fichiers": 3, "nb_lignes": 1500}


def transform(**context):
    stats = context["ti"].xcom_pull(task_ids="extract")
    print(f"[ TRANSFORM ] Nettoyage de {stats['nb_lignes']} lignes")
    print("  -> Suppression des doublons")
    print("  -> Conversion des types")
    nb_clean = int(stats["nb_lignes"] * 0.95)
    print(f"  -> {nb_clean} lignes conservées après nettoyage")
    return {"nb_lignes_clean": nb_clean}


def load(**context):
    stats = context["ti"].xcom_pull(task_ids="transform")
    print(f"[ LOAD ] Écriture de {stats['nb_lignes_clean']} lignes en Parquet")
    print("  -> Partition par date")
    print("  -> Écriture dans curated/ : OK")


with DAG(
    dag_id="example_pipeline",
    description="Pipeline Raw → Cleansed → Curated (exemple)",
    start_date=datetime(2026, 3, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
    tags=["exemple", "formation"],
) as dag:

    t_extract = PythonOperator(
        task_id="extract",
        python_callable=extract,
    )

    t_transform = PythonOperator(
        task_id="transform",
        python_callable=transform,
    )

    t_load = PythonOperator(
        task_id="load",
        python_callable=load,
    )

    t_extract >> t_transform >> t_load
