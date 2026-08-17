from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

def ingest_bronze(**context):
    print(f"[Bronze] Ingestion date : {context['ds']}")
    print("[Bronze] Lecture JSON raw/orders/2026/03/ → écriture bronze/orders/")
    print("[Bronze] 200 événements ingérés.")

def transform_silver(**context):
    print(f"[Silver] Transformation date : {context['ds']}")
    print("[Silver] Typage, déduplication event_id, calcul total_price")
    print("[Silver] 200 lignes valides → silver/orders/")

def aggregate_gold(**context):
    print(f"[Gold] Agrégation date : {context['ds']}")
    print("[Gold] CA par jour et produit → gold/orders_daily/")
    ca = 200 * 59.5
    print(f"[Gold] CA total estimé : {ca:.2f}")

with DAG(
    dag_id="orders_pipeline",
    description="Pipeline commandes : Bronze → Silver → Gold",
    schedule_interval="0 6 * * *",
    start_date=datetime(2026, 3, 1),
    catchup=False,
    default_args={
        "owner": "data-engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["orders", "data-engineering"],
) as dag:

    task_bronze = PythonOperator(task_id="ingest_bronze",   python_callable=ingest_bronze)
    task_silver = PythonOperator(task_id="transform_silver", python_callable=transform_silver)
    task_gold   = PythonOperator(task_id="aggregate_gold",   python_callable=aggregate_gold)

    task_bronze >> task_silver >> task_gold
