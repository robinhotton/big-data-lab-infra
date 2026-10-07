"""Tests de airflow/src/load.py — couche Gold (agrégation + écriture MinIO).

`aggregate_gold` est du Python pur : testé directement.
Les fonctions d'écriture sont testées avec `moto` (skipé si absent).
"""
from __future__ import annotations

import json

import pytest
from load import aggregate_gold

# --- aggregate_gold : agrégation CA par status (sans pandas) ---------------

def _silver(event_id="a", status="completed", total_price=10.0):
    return {
        "event_id": event_id,
        "timestamp": "2026-03-01T10:00:00Z",
        "user_id": "u1",
        "product_id": "p1",
        "quantity": 1,
        "price": total_price,
        "status": status,
        "total_price": total_price,
    }


def test_aggregate_gold_sums_by_status():
    events = [
        _silver("a", "completed", 10.0),
        _silver("b", "completed", 5.5),
        _silver("c", "pending", 2.0),
    ]
    gold = aggregate_gold(events)

    assert gold["ca_by_status"] == {"completed": 15.5, "pending": 2.0}
    assert gold["total_events"] == 3
    assert gold["total_ca"] == 17.5


def test_aggregate_gold_empty():
    gold = aggregate_gold([])
    assert gold["ca_by_status"] == {}
    assert gold["total_events"] == 0
    assert gold["total_ca"] == 0


def test_aggregate_gold_rounds_to_two_decimals():
    gold = aggregate_gold([_silver("a", "completed", 0.1), _silver("b", "completed", 0.2)])
    # 0.1 + 0.2 = 0.30000000000000004 en flottant → arrondi au centime
    assert gold["ca_by_status"]["completed"] == 0.3
    assert gold["total_ca"] == 0.3


# --- Écriture MinIO (moto) -------------------------------------------------

@pytest.fixture
def moto_env(monkeypatch):
    """Client S3 mocké + env injecté dans load/extract."""
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")

    with moto.mock_aws():
        s3 = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        s3.create_bucket(Bucket="data-lake")
        monkeypatch.setenv("MINIO_BUCKET", "data-lake")
        monkeypatch.setattr("load.get_s3_client", lambda: s3)
        yield s3


def test_write_json_to_minio_is_idempotent(moto_env):
    """Clé datée : un re-run écrase sans créer de doublon (idempotence Gold)."""
    from load import write_json_to_minio

    write_json_to_minio("curated/ca_by_status_2026-03-01.json", {"total_ca": 1})
    write_json_to_minio("curated/ca_by_status_2026-03-01.json", {"total_ca": 2})

    listed = moto_env.list_objects_v2(Bucket="data-lake", Prefix="curated/")
    keys = [o["Key"] for o in listed.get("Contents", [])]
    assert keys == ["curated/ca_by_status_2026-03-01.json"], f"doublon créé : {keys}"

    body = moto_env.get_object(Bucket="data-lake", Key=keys[0])["Body"].read()
    assert json.loads(body) == {"total_ca": 2}


def test_write_quarantine_noop_when_empty(moto_env):
    """Aucun invalide → aucune écriture (pas de fichier quarantine vide)."""
    from load import write_quarantine

    write_quarantine([], "2026-03-01")

    listed = moto_env.list_objects_v2(Bucket="data-lake", Prefix="quarantine/")
    assert "Contents" not in listed


def test_write_quarantine_writes_rejects(moto_env):
    from load import write_quarantine

    write_quarantine([{"event_id": "x", "_reject_reason": "price <= 0"}], "2026-03-01")

    body = moto_env.get_object(
        Bucket="data-lake", Key="quarantine/orders/2026-03-01.json"
    )["Body"].read()
    payload = json.loads(body)
    assert payload["rejected"][0]["_reject_reason"] == "price <= 0"
