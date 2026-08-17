"""
Tests de airflow/src/config.py — centralisation de la config via env vars.

Vérifie que MinIOConfig lit bien les variables d'environnement (comportement
attendu côté conteneur, où docker-compose injecte MINIO_*).
"""
from __future__ import annotations

from src.config import MinIOConfig


def test_minio_config_reads_env(monkeypatch):
    """MinIOConfig doit lire les vars d'environnement à l'instanciation."""
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("MINIO_BUCKET", "my-bucket")

    cfg = MinIOConfig()
    assert cfg.endpoint == "http://minio:9000"
    assert cfg.access_key == "ak"
    assert cfg.secret_key == "sk"
    assert cfg.bucket == "my-bucket"


def test_minio_config_defaults(monkeypatch):
    """Sans env vars, endpoint et bucket ont des valeurs par défaut ; les
    credentials sont obligatoires (fail-safe : pas de fallback en clair)."""
    for var in ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET"):
        monkeypatch.delenv(var, raising=False)

    # endpoint/bucket : défauts non sensibles.
    # On valide via __post_init__ partiel en posant juste les creds pour ne pas
    # déclencher le fail-safe.
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    cfg = MinIOConfig()
    assert cfg.bucket == "data-lake"
    assert cfg.endpoint == "http://minio:9000"


def test_minio_config_fails_without_credentials(monkeypatch):
    """Sans credentials MinIO, MinIOConfig refuse de s'instancier (fail-safe)."""
    for var in ("MINIO_ACCESS_KEY", "MINIO_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)

    import pytest
    with pytest.raises(RuntimeError, match="MINIO_ACCESS_KEY/MINIO_SECRET_KEY"):
        MinIOConfig()


def test_s3_url():
    """s3_url(key) construit l'URI s3://bucket/key (méthode simple, pas une property)."""
    cfg = MinIOConfig()
    cfg.bucket = "data-lake"
    assert cfg.s3_url("raw/orders/2026/03/orders_2026-03-15.json") == \
        "s3://data-lake/raw/orders/2026/03/orders_2026-03-15.json"
