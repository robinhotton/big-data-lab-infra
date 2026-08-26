"""load.py — Gold : agrégation CA et écriture idempotente dans MinIO (Python pur).

Version *lab* de `CODE/load.py` du cours (cours-big-data-local-2j). Mêmes contrats :
`aggregate_gold`, `write_json_to_minio`, `write_quarantine`, `load_gold`.

Silver → Gold : on agrège le CA par status, on écrit `curated/ca_by_status_{ds}.json`
de façon idempotente (clé datée → un re-run écrase sans créer de doublon), et les
invalides de Silver partent en `quarantine/orders/{ds}.json` (pattern Quarantine).

Sans pandas ni Spark : agrégation via `collections.Counter`.
"""
from __future__ import annotations

import collections
import json

from config import get_s3_client, MinIOConfig
from transform import transform_silver


def aggregate_gold(events: list[dict]) -> dict:
    """Agrège le CA par status à partir des événements Silver (sans pandas)."""
    ca = collections.Counter()
    for e in events:
        ca[e["status"]] += e["total_price"]
    return {
        "ca_by_status": {k: round(v, 2) for k, v in ca.items()},
        "total_events": len(events),
        "total_ca": round(sum(ca.values()), 2),
    }


def write_json_to_minio(key: str, payload: dict) -> None:
    """Écrit un dict en JSON dans MinIO (mode overwrite : clé datée = idempotent)."""
    cfg = MinIOConfig.from_env()
    s3 = get_s3_client()
    body = json.dumps(payload, indent=2).encode("utf-8")
    s3.put_object(Bucket=cfg.bucket, Key=key, Body=body)
    print(f"[Gold] écrit {len(body)} octets -> {key}")


def write_quarantine(invalid: list[dict], ds: str) -> None:
    """Écrit les événements invalides en quarantine (pattern Quarantine)."""
    if not invalid:
        return
    write_json_to_minio(f"quarantine/orders/{ds}.json", {"rejected": invalid})


def load_gold(ds: str = "2026-03-01") -> dict:
    """Pipeline Gold complet : extract Bronze -> transform Silver -> agrège + écrit.

    Retourne les métriques Gold (ca_by_status, total_events, total_ca).
    """
    from extract import extract_bronze  # import local : évite les cycles config->extract

    events = extract_bronze(ds)
    valid, invalid = transform_silver(events)

    gold = aggregate_gold(valid)
    write_json_to_minio(f"curated/ca_by_status_{ds}.json", gold)
    write_quarantine(invalid, ds)

    print(f"[Gold] CA par status pour {ds} : {gold['ca_by_status']}")
    return gold


if __name__ == "__main__":
    load_gold("2026-03-01")
