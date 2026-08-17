from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def hello():
    print("DAG binome11 OK — pipeline visible dans Airflow.")

with DAG(
    dag_id="test_binome11",
    start_date=datetime(2026, 3, 1),
    schedule=None,
    catchup=False,
    tags=["test", "binome11"],
) as dag:
    PythonOperator(task_id="hello", python_callable=hello)
