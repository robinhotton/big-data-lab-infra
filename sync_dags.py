"""
sync_dags.py — Synchronise les DAGs déposés par les binômes dans MinIO
               vers le dossier local ./airflow/dags/.

Usage :
    python sync_dags.py
    python sync_dags.py --endpoint http://[hidora-url]:9000 --nb-binomes 7

Le fichier attendu dans chaque bucket : dags/dag_orders.py
Il est renommé dag_orders_binomeXX.py pour éviter les conflits dans Airflow.
"""

import argparse
import os
import boto3
from botocore.exceptions import ClientError

DEFAULT_DAGS_DIR = os.path.join(os.path.dirname(__file__), "airflow", "dags")

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint",      default="http://localhost:9000")
    p.add_argument("--access-key",    default="minioadmin")
    p.add_argument("--secret-key",    default="minioadmin123")
    p.add_argument("--prefix-bucket", default="data-lake-binome")
    p.add_argument("--nb-binomes",    type=int, default=7)
    p.add_argument("--dag-key",       default="dags/dag_orders.py",
                   help="Chemin du DAG dans le bucket MinIO")
    p.add_argument("--dags-dir",      default=DEFAULT_DAGS_DIR,
                   help="Dossier local dags/ surveillé par Airflow")
    return p.parse_args()

def main():
    args = parse_args()
    os.makedirs(args.dags_dir, exist_ok=True)

    s3 = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
    )

    synced = 0
    for i in range(1, args.nb_binomes + 1):
        bucket = f"{args.prefix_bucket}-{i:02d}"
        binome_dir = os.path.join(args.dags_dir, f"binome{i:02d}")
        os.makedirs(binome_dir, exist_ok=True)
        dest = os.path.join(binome_dir, "dag_orders.py")
        try:
            s3.download_file(bucket, args.dag_key, dest)
            print(f"  [OK] {bucket}/{args.dag_key} -> {dest}")
            synced += 1
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("404", "NoSuchKey"):
                print(f"  [--] {bucket} : pas encore de DAG")
            else:
                print(f"  [ERR] {bucket} : {e}")

    print(f"\n{synced}/{args.nb_binomes} DAG(s) synchronisé(s) dans {args.dags_dir}")

if __name__ == "__main__":
    main()
