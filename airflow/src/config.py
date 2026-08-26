"""config.py — Configuration MinIO du pipeline orders (Python pur, alignée sur le cours).

FACTEUR DE PATCH : ce fichier est la version *lab* de `CODE/config.py` du dépôt de
cours (cours-big-data-local-2j). Il en reprend le contrat (dataclass `MinIOConfig`,
`from_env()`, `get_s3_client()`), mais les valeurs par défaut pointent vers le réseau
Docker du lab (endpoint `http://minio:9000`, credentials explicites) alors que
`CODE/config.py` vise un usage hors Docker (`localhost:9000`).

Il fonctionne dans les deux contextes d'import :
  - `from config import ...`  (modules métier copiés dans airflow/src/, ex. TP2) ;
  - `from src.config import ...`  (DAG du lab exécuté par Airflow, PYTHONPATH=/opt/airflow).

Les valeurs sont lues depuis l'environnement à l'instanciation (variables injectées
par docker-compose, ou .env en local). Pour un usage hors Docker depuis la machine
hôte, définir `MINIO_ENDPOINT=http://localhost:9000`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MinIOConfig:
    """Connexion MinIO (S3-compatible). Lue depuis l'environnement à l'instanciation."""

    endpoint: str
    access_key: str
    secret_key: str
    bucket: str

    @classmethod
    def from_env(cls) -> "MinIOConfig":
        """Construit la config depuis l'environnement.

        Le défaut d'endpoint est `http://minio:9000` (réseau Docker du lab). Pour un
        usage *hors Docker* (depuis la machine hôte, ex. notebook/tests), définir
        `MINIO_ENDPOINT=http://localhost:9000`.
        """
        return cls(
            endpoint=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
            bucket=os.getenv("MINIO_BUCKET", "data-lake"),
        )


def get_s3_client():
    """Construit un client boto3 pointant vers MinIO (S3-compatible).

    `boto3` est importé localement : c'est une dépendance du pipeline, pas de la
    configuration — ça permet d'importer ce module sans boto3 installé (ex. tests).
    """
    import boto3

    cfg = MinIOConfig.from_env()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
    )
