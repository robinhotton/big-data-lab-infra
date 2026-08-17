"""
Config du pipeline orders — centralise endpoints MinIO, bucket et chemins.

Lu via variables d'environnement (renseignées par docker-compose, ou .env en local).
Les valeurs sont lues dans __post_init__ (pas en valeur par défaut de champ) pour
qu'elles soient réévaluées à chaque instanciation — nécessaire pour les tests
(monkeypatch.setenv) et cohérent avec l'injection d'env vars par le conteneur.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass
class MinIOConfig:
    """Connexion MinIO (S3-compatible). Lue depuis l'environnement à l'instanciation."""
    endpoint:   str = ""
    access_key: str = ""
    secret_key: str = ""
    bucket:     str = ""

    def __post_init__(self):
        self.endpoint   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.bucket     = os.getenv("MINIO_BUCKET", "data-lake")

    def s3_url(self, key: str) -> str:
        """Construit l'URI s3://bucket/key pour un objet donné."""
        return f"s3://{self.bucket}/{key}"

    def client(self):
        """Construit un client boto3 S3 pointant sur MinIO."""
        import boto3
        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )


@dataclass
class PathsConfig:
    """Chemins de staging Parquet (volume partagé monté dans le conteneur)."""
    staging: Path = field(default_factory=lambda: Path("/opt/airflow/data/staging"))
    reports:  Path = field(default_factory=lambda: Path("/opt/airflow/data/reports"))

    def __post_init__(self):
        self.staging.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)


@dataclass
class ETLConfig:
    minio: MinIOConfig  = field(default_factory=MinIOConfig)
    paths: PathsConfig  = field(default_factory=PathsConfig)


# Instance globale — importée par extract/transform/load et le DAG.
# Les valeurs sont figées à l'import (au démarrage du conteneur) ; pour des valeurs
# fraîches (tests), instancier explicitement ETLConfig().
config = ETLConfig()


if __name__ == "__main__":
    print("=== Pipeline orders — Config ===")
    print(f"MinIO endpoint : {config.minio.endpoint}")
    print(f"Bucket         : {config.minio.bucket}")
    print(f"Staging        : {config.paths.staging}")
    print("Config OK")
