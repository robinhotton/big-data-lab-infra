"""Tests de airflow/src/config.py — config MinIO via variables d'environnement.

Alignés sur CODE/config.py du cours et la nouvelle version Python pur du lab
(dataclass MinIOConfig frozen + from_env()), sans pandas ni pyarrow.
"""
from __future__ import annotations

import pytest

from config import MinIOConfig

MONKEYPATCH_VARS = ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET")


def test_minio_config_reads_env(monkeypatch):
    """from_env() lit les variables d'environnement à l'instanciation."""
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "ak")
    monkeypatch.setenv("MINIO_SECRET_KEY", "sk")
    monkeypatch.setenv("MINIO_BUCKET", "my-bucket")

    cfg = MinIOConfig.from_env()
    assert cfg.endpoint == "http://minio:9000"
    assert cfg.access_key == "ak"
    assert cfg.secret_key == "sk"
    assert cfg.bucket == "my-bucket"


def test_minio_config_defaults(monkeypatch):
    """Sans variables d'environnement, les valeurs de lab sont utilisées par défaut.

    endpoint=minio:9000 (réseau Docker), credentials/bucket = valeurs de lab.
    """
    for var in MONKEYPATCH_VARS:
        monkeypatch.delenv(var, raising=False)

    cfg = MinIOConfig.from_env()
    assert cfg.endpoint == "http://minio:9000"
    assert cfg.access_key == "minioadmin"
    assert cfg.secret_key == "minioadmin123"
    assert cfg.bucket == "data-lake"


def test_get_s3_client_builds(monkeypatch):
    """get_s3_client() construit un client boto3 pointant vers l'endpoint MinIO.

    boto3 ne contacte pas le serveur à l'instanciation : ce test reste hors-ligne.
    """
    pytest.importorskip("boto3")
    monkeypatch.setenv("MINIO_ENDPOINT", "http://localhost:9000")

    from config import get_s3_client

    s3 = get_s3_client()
    assert s3.meta.endpoint_url == "http://localhost:9000"
