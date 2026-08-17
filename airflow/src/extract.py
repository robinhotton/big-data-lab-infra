"""
Extract — lit les événements JSON raw/orders depuis MinIO → Parquet de staging.

Source : s3://data-lake/raw/orders/{year}/{month:02d}/orders_{ds}.json
Sortie  : staging/orders_raw.parquet  (JSON Lines, 1 événement par ligne)
"""
import json
import logging
import io

import pandas as pd

from src.config import config

logger = logging.getLogger(__name__)


def extract_orders(ds: str) -> pd.DataFrame:
    """
    Extrait les événements de commandes d'un jour logique (ds = YYYY-MM-DD).

    Args:
        ds: date logique au format YYYY-MM-DD (fourni par Airflow via {{ ds }}).

    Returns:
        DataFrame pandas des événements (colonnes event_id, timestamp, user_id,
        product_id, quantity, price, status). Vide si aucun fichier pour ce jour.
    """
    year, month, day = ds.split("-")
    key = f"raw/orders/{year}/{month}/orders_{ds}.json"

    s3 = config.minio.client()
    bucket = config.minio.bucket

    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
    except s3.exceptions.NoSuchKey:
        logger.warning("Aucun fichier orders pour %s (s3://%s/%s)", ds, bucket, key)
        return pd.DataFrame(columns=[
            "event_id", "timestamp", "user_id", "product_id",
            "quantity", "price", "status",
        ])

    content = resp["Body"].read().decode("utf-8")
    rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    df = pd.DataFrame(rows)
    logger.info("Extract OK — %d événements lus pour %s", len(df), ds)

    # Staging Parquet pour la tâche transform
    out = config.paths.staging / "orders_raw.parquet"
    df.to_parquet(out, index=False)
    logger.info("Staging écrit : %s", out)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    df = extract_orders("2026-03-15")
    print(df.head())
    print(f"Colonnes : {list(df.columns)}")
