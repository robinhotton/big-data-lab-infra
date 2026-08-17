"""
Transform — nettoyage et enrichissement des orders (couche Silver).

Entrée : staging/orders_raw.parquet  (écrit par extract.py)
Sortie  : staging/orders_silver.parquet

Étapes :
  - typage (quantity int, price float, timestamp datetime)
  - déduplication sur event_id (idempotence si relecture de la même journée)
  - calcul total_price = quantity * price
  - filtrage des orders non valides (status cancelled hors périmètre analytique)
"""
import logging

import pandas as pd

from src.config import config

logger = logging.getLogger(__name__)


def transform_orders(ds: str) -> pd.DataFrame:
    """
    Transforme les orders bruts en couche Silver propre.

    Args:
        ds: date logique (pour log et partitionnement).

    Returns:
        DataFrame Silver (colonnes Silver + total_price). Vide si l'extract était vide.
    """
    raw_path = config.paths.staging / "orders_raw.parquet"
    df = pd.read_parquet(raw_path)

    if df.empty:
        logger.warning("Transform — aucune order à traiter pour %s", ds)
        silver = pd.DataFrame()
    else:
        n_in = len(df)

        # Typage
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").astype("Int64")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

        # Déduplication sur event_id (idempotence)
        df = df.drop_duplicates(subset=["event_id"], keep="first")

        # Enrichissement
        df["total_price"] = df["quantity"].astype(float) * df["price"]

        # Filtre analytique : on garde les orders validées (completed / pending)
        df = df[df["status"].isin(["completed", "pending"])].copy()

        silver = df.reset_index(drop=True)
        logger.info(
            "Transform OK — %d → %d lignes pour %s (dédup + filtre status)",
            n_in, len(silver), ds,
        )

    out = config.paths.staging / "orders_silver.parquet"
    silver.to_parquet(out, index=False)
    logger.info("Staging écrit : %s", out)
    return silver


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
    silver = transform_orders("2026-03-15")
    print(silver.head())
    print(f"Colonnes : {list(silver.columns)}")
