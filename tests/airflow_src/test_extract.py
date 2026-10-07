"""Tests de airflow/src/extract.py — couche Bronze (lecture MinIO).

Deux niveaux :
  - unitaires, avec un client S3 factice (rapide, déterministe, hors réseau) ;
  - intégration avec `moto`, pour valider le vrai contrat S3 (skipé si absent).

Le test clé est la **pagination** : `ListObjectsV2` renvoie au plus 1000 clés
par appel. Sans suivi de `ContinuationToken`, `list_orders_for_date` perdait
silencieusement les fichiers au-delà de ce seuil (voir docs/AUDIT.md, A2).
"""
from __future__ import annotations

import pytest
from extract import _list_keys, list_orders_for_date, parse_jsonl

# --- parse_jsonl : contrat du format JSON Lines du lab ----------------------

def test_parse_jsonl_one_object_per_line():
    raw = b'{"event_id":"a"}\n{"event_id":"b"}\n'
    assert parse_jsonl(raw) == [{"event_id": "a"}, {"event_id": "b"}]


def test_parse_jsonl_skips_blank_lines():
    raw = b'{"event_id":"a"}\n\n   \n{"event_id":"b"}\n'
    assert [e["event_id"] for e in parse_jsonl(raw)] == ["a", "b"]


def test_parse_jsonl_empty_returns_empty_list():
    assert parse_jsonl(b"") == []


# --- _list_keys : pagination ----------------------------------------------

class FakeS3Paged:
    """Client S3 factice qui simule `ListObjectsV2` paginé (1000 clés/page).

    Plus rapide et plus lisible qu'un vrai serveur pour tester la logique de
    suivi de `ContinuationToken`.
    """

    def __init__(self, keys: list[str], page_size: int = 1000):
        self.keys = list(keys)
        self.page_size = page_size
        self.calls = 0  # nb d'appels émis — pour prouver qu'on a paginé

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        self.calls += 1
        matched = [k for k in self.keys if k.startswith(Prefix)]
        start = int(ContinuationToken) if ContinuationToken else 0
        page = matched[start : start + self.page_size]
        truncated = (start + self.page_size) < len(matched)
        resp = {"Contents": [{"Key": k} for k in page]}
        if truncated:
            resp["IsTruncated"] = True
            resp["NextContinuationToken"] = str(start + self.page_size)
        return resp


def test_list_keys_single_page_no_token():
    fake = FakeS3Paged(["raw/a.json", "raw/b.json"], page_size=1000)
    assert _list_keys(fake, "bkt", "raw/") == ["raw/a.json", "raw/b.json"]
    assert fake.calls == 1


def test_list_keys_follows_pagination_beyond_1000():
    """1500 clés : le 1er appel n'en renvoie que 1000 — les 500 manquantes
    doivent être ramenées par la pagination, sinon le pipeline les perd."""
    keys = [f"raw/orders/2026/03/orders_2026-03-01-{i:05d}.json" for i in range(1500)]
    fake = FakeS3Paged(keys, page_size=1000)

    found = _list_keys(fake, "bkt", "raw/orders/2026/03/")

    assert len(found) == 1500, f"pagination cassée : {len(found)}/1500 clés ramenées"
    assert fake.calls == 2, "deux pages attendues (1000 + 500)"


def test_list_keys_three_pages():
    keys = [f"k{i:05d}" for i in range(2500)]
    fake = FakeS3Paged(keys, page_size=1000)
    assert len(_list_keys(fake, "bkt", "k")) == 2500
    assert fake.calls == 3


def test_list_orders_for_date_filters_on_ds(monkeypatch):
    """Un préfixe de mois contient 31 jours : seules les clés du `ds` demandé
    sont conservées."""
    keys = [
        "raw/orders/2026/03/orders_2026-03-01.json",
        "raw/orders/2026/03/orders_2026-03-02.json",
        "raw/orders/2026/03/orders_2026-03-01-00001.json",  # autre suffixe
    ]
    fake = FakeS3Paged(keys)

    monkeypatch.setattr("extract.get_s3_client", lambda: fake)
    monkeypatch.setenv("MINIO_BUCKET", "data-lake")

    got = list_orders_for_date("2026-03-01")
    assert got == ["raw/orders/2026/03/orders_2026-03-01.json"]


# --- Intégration moto (optionnelle) ----------------------------------------

@pytest.fixture
def moto_s3(monkeypatch):
    """Vrai client S3 mocké par moto, prêt à être injecté dans extract."""
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
        monkeypatch.setattr("extract.get_s3_client", lambda: s3)
        yield s3


def test_extract_bronze_end_to_end(moto_s3):
    """Le vrai contrat S3 : écriture puis relecture Bronze.

    Nommage du lab : un fichier par jour, `raw/orders/YYYY/MM/orders_YYYY-MM-DD.json`
    contenant du JSON Lines (un événement par ligne).
    """
    from extract import extract_bronze

    moto_s3.put_object(
        Bucket="data-lake",
        Key="raw/orders/2026/03/orders_2026-03-01.json",
        Body=b'{"event_id":"e0"}\n{"event_id":"e1"}\n\n{"event_id":"e2"}\n',
    )
    moto_s3.put_object(  # jour voisin : ne doit PAS être lu
        Bucket="data-lake",
        Key="raw/orders/2026/03/orders_2026-03-02.json",
        Body=b'{"event_id":"other"}\n',
    )

    events = extract_bronze("2026-03-01")
    assert [e["event_id"] for e in events] == ["e0", "e1", "e2"]
