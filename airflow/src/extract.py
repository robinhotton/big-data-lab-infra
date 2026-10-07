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
import logging

from config import MinIOConfig, get_s3_client

logger = logging.getLogger(__name__)


def parse_jsonl(raw: bytes) -> list[dict]:
    """Parse du JSON Lines : un objet JSON par ligne (ignore les lignes vides)."""
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def _list_keys(s3, bucket: str, prefix: str) -> list[str]:
    """Toutes les clés sous `prefix`, **toutes pages confondues**.

    `ListObjectsV2` renvoie au plus 1000 clés par appel : sans pagination, tout
    ce qui dépasse est silencieusement ignoré (le pipeline perd des données
    sans erreur). On suit `ContinuationToken` jusqu'à épuisement.
    """
    keys: list[str] = []
    token: str | None = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        keys.extend(obj["Key"] for obj in resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            return keys
        token = resp.get("NextContinuationToken")


def list_orders_for_date(ds: str) -> list[str]:
    """Liste les clés des fichiers orders d'une date logique (ds = `YYYY-MM-DD`).

    Le dataset du lab est partitionné : `raw/orders/YYYY/MM/orders_YYYY-MM-DD.json`.
    """
    cfg = MinIOConfig.from_env()
    s3 = get_s3_client()
    year, month, _ = ds.split("-")
    prefix = f"raw/orders/{year}/{month}/"
    return [k for k in _list_keys(s3, cfg.bucket, prefix) if k.endswith(f"orders_{ds}.json")]


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

    logger.info("Bronze : %s événement(s) lus pour %s", len(events), ds)
    return events


if __name__ == "__main__":
    ev = extract_bronze("2026-03-01")
    print(f"Premier : {ev[0] if ev else 'vide'}")
