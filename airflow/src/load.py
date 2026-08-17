"""
Load — agrégation Gold et écriture idempotente dans MinIO.

Entrée : staging/orders_silver.parquet  (écrit par transform.py)
Sortie : s3://data-lake/gold/orders_daily/ds=YYYY-MM-DD/orders_daily.parquet

L'écriture est partitionnée par date logique (ds) et écrase la partition du jour :
rejouer le DAG pour la même date ne crée jamais de doublon (idempotence).
"""
import logging
import io

import pandas as pd

from src.config import config

logger = logging.getLogger(__name__)


def load_gold(ds: str) -> dict:
    """
    Agrège les orders Silver en CA par jour et produit (couche Gold),
    puis écrit le résultat dans MinIO, partitionné par date.

    Args:
        ds: date logique (utilisé pour la partition ds=YYYY-MM-DD).

    Returns:
        Dict de métriques {"nb_lignes_gold": int, "ca_total": float}.
    """
    silver_path = config.paths.staging / "orders_silver.parquet"
    df = pd.read_parquet(silver_path)

    if df.empty:
        logger.warning("Load — aucune order Silver pour %s, Gold vide", ds)
        return {"nb_lignes_gold": 0, "ca_total": 0.0}

    # Agrégation Gold : CA par jour + produit
    df["order_date"] = pd.to_datetime(df["timestamp"]).dt.date
    gold = (
        df.groupby(["order_date", "product_id"], as_index=False)
          .agg(
              nb_orders=("event_id", "count"),
              ca_total=("total_price", "sum"),
          )
    )
    gold["ds"] = ds

    # Écriture idempotente dans MinIO (partition ds=YYYY-MM-DD)
    s3 = config.minio.client()
    bucket = config.minio.bucket
    key = f"gold/orders_daily/ds={ds}/orders_daily.parquet"

    parquet_bytes = gold.to_parquet(index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=parquet_bytes)
    logger.info("Load OK — %d lignes Gold écrites → s3://%s/%s", len(gold), bucket, key)

    return {"nb_lignes_gold": len(gold), "ca_total": float(gold["ca_total"].sum())}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    metrics = load_gold("2026-03-15")
    print(metrics)
