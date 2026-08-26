"""extract.py — Bronze : lire les JSON orders de MinIO (Python pur, sans pandas).

Version *lab* de `CODE/extract.py` du cours (cours-big-data-local-2j). Mêmes contrats :
`parse_jsonl`, `list_orders_for_date`, `extract_bronze`.

Bronze = ingestion brute : on lit les fichiers JSON `raw/orders/` du jour et on
retourne une liste d'événements. Aucune transformation ici — juste la lecture.

Format des fichiers : **JSON Lines** (.json), un événement par ligne — c'est le format
généré par `setup_datasets.py` du lab. On lit ligne à ligne ; un `json.loads()` sur le
fichier entier échouerait (`Extra data`).
"""
from __future__ import annotations

import json

from config import get_s3_client, MinIOConfig


def parse_jsonl(raw: bytes) -> list[dict]:
    """Parse du JSON Lines : un objet JSON par ligne (ignore les lignes vides)."""
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def list_orders_for_date(ds: str) -> list[str]:
    """Liste les clés des fichiers orders d'une date logique (ds = `YYYY-MM-DD`).

    Le dataset du lab est partitionné : `raw/orders/YYYY/MM/orders_YYYY-MM-DD.json`.
    """
    cfg = MinIOConfig.from_env()
    s3 = get_s3_client()
    year, month, _ = ds.split("-")
    prefix = f"raw/orders/{year}/{month}/"
    resp = s3.list_objects_v2(Bucket=cfg.bucket, Prefix=prefix)
    keys = [
        obj["Key"]
        for obj in resp.get("Contents", [])
        if obj["Key"].endswith(f"orders_{ds}.json")
    ]
    return keys


def extract_bronze(ds: str = "2026-03-01") -> list[dict]:
    """Lit tous les events JSON du jour et retourne une liste plate d'événements.

    Lecture en mémoire (`BytesIO`) — pas de fichier temporaire sur disque.
    """
    cfg = MinIOConfig.from_env()
    s3 = get_s3_client()
    events: list[dict] = []

    for key in list_orders_for_date(ds):
        resp = s3.get_object(Bucket=cfg.bucket, Key=key)
        events.extend(parse_jsonl(resp["Body"].read()))  # JSON Lines -> list[dict]

    print(f"[Bronze] {len(events)} événement(s) lus pour {ds}")
    return events


if __name__ == "__main__":
    ev = extract_bronze("2026-03-01")
    print(f"Premier : {ev[0] if ev else 'vide'}")
