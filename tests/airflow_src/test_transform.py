"""
Tests de airflow/src/transform.py — couche Silver.

transform_orders() est testée SANS MinIO : on injecte un Parquet raw jouet dans
le dossier de staging (redirigé via la fixture `staging_dir`), puis on vérifie :
  - déduplication sur event_id (idempotence si relecture) ;
  - calcul de total_price = quantity * price ;
  - filtrage des status non analytiques (cancelled exclus).

Nécessite pyarrow (to_parquet/read_parquet) — skip si absent.
"""
from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from src.transform import transform_orders  # noqa: E402


def _write_raw(staging_dir, rows):
    """Écrit un Parquet raw jouet à l'emplacement attendu par transform_orders."""
    df = pd.DataFrame(rows)
    df.to_parquet(staging_dir / "orders_raw.parquet", index=False)


def test_transform_dedup_and_total_price(staging_dir):
    """Dédup sur event_id + calcul total_price = quantity * price."""
    rows = [
        {"event_id": "e1", "timestamp": "2026-03-15T10:00:00Z",
         "user_id": "usr-0001", "product_id": "prod-001",
         "quantity": 2, "price": 10.0, "status": "completed"},
        # Doublon de e1 (même event_id) → doit être dédupliqué
        {"event_id": "e1", "timestamp": "2026-03-15T10:00:00Z",
         "user_id": "usr-0001", "product_id": "prod-001",
         "quantity": 2, "price": 10.0, "status": "completed"},
        {"event_id": "e2", "timestamp": "2026-03-15T11:00:00Z",
         "user_id": "usr-0002", "product_id": "prod-002",
         "quantity": 3, "price": 5.0, "status": "pending"},
    ]
    _write_raw(staging_dir, rows)

    silver = transform_orders("2026-03-15")

    # 3 lignes en entrée, 1 doublon → 2 lignes en sortie
    assert len(silver) == 2
    assert set(silver["event_id"]) == {"e1", "e2"}

    # total_price correct
    by_id = silver.set_index("event_id")
    assert by_id.loc["e1", "total_price"] == 20.0   # 2 × 10
    assert by_id.loc["e2", "total_price"] == 15.0   # 3 × 5


def test_transform_filters_cancelled(staging_dir):
    """Les status 'cancelled' sont exclus du périmètre analytique."""
    rows = [
        {"event_id": "e1", "timestamp": "2026-03-15T10:00:00Z",
         "user_id": "usr-0001", "product_id": "prod-001",
         "quantity": 1, "price": 9.99, "status": "completed"},
        {"event_id": "e2", "timestamp": "2026-03-15T11:00:00Z",
         "user_id": "usr-0002", "product_id": "prod-002",
         "quantity": 1, "price": 19.99, "status": "cancelled"},
    ]
    _write_raw(staging_dir, rows)

    silver = transform_orders("2026-03-15")

    # Seul e1 (completed) survit — e2 (cancelled) est filtré
    assert len(silver) == 1
    assert silver.iloc[0]["event_id"] == "e1"


def test_transform_empty_input(staging_dir):
    """Un Parquet raw vide → DataFrame Silver vide (pas d'erreur)."""
    _write_raw(staging_dir, [])
    silver = transform_orders("2026-03-15")
    assert silver.empty
