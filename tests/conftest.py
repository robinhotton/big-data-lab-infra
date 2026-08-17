"""
Fixtures partagées pour les tests de airflow/src/.

Ces tests s'exécutent SANS Docker et SANS MinIO :
  - la config MinIO n'est pas utilisée (transform lit/écrit dans staging local) ;
  - on redirige config.paths.staging vers un dossier temporaire pytest.

Usage :
    pytest                       # lance tous les tests
    pytest tests/airflow_src/    # uniquement les tests du métier
    pytest -k transform          # filtre par nom
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Rendre airflow/src importable (le dépôt n'est pas un package installé).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "airflow"))

# Variables d'env factices pour que config.py (qui lit os.getenv) ne plante pas.
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin123")
os.environ.setdefault("MINIO_BUCKET", "data-lake")


@pytest.fixture
def staging_dir(tmp_path, monkeypatch):
    """Redirige config.paths.staging vers un dossier temporaire isolé par test."""
    from src.config import config

    staging = tmp_path / "staging"
    staging.mkdir()
    monkeypatch.setattr(config.paths, "staging", staging)
    monkeypatch.setattr(config.paths, "reports", tmp_path / "reports")
    return staging
