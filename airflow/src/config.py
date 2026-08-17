"""
Config du pipeline orders — centralise endpoints MinIO, bucket et chemins.

Lu via variables d'environnement (renseignées par docker-compose, ou .env en local).
Pattern identique à agrosmart-airflow/src/config.py.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass
class MinIOConfig:
    """Connexion MinIO (S3-compatible)."""
    endpoint:    str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    access_key:  str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key:  str = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
    bucket:      str = os.getenv("MINIO_BUCKET", "data-lake")

    @property
    def s3_url(self, key: str) -> str:
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
    staging: Path = Path("/opt/airflow/data/staging")
    reports:  Path = Path("/opt/airflow/data/reports")

    def __post_init__(self):
        self.staging.mkdir(parents=True, exist_ok=True)
        self.reports.mkdir(parents=True, exist_ok=True)


@dataclass
class ETLConfig:
    minio: MinIOConfig  = field(default_factory=MinIOConfig)
    paths: PathsConfig  = field(default_factory=PathsConfig)


# Instance globale — importée par extract/transform/load et le DAG
config = ETLConfig()


if __name__ == "__main__":
    print("=== Pipeline orders — Config ===")
    print(f"MinIO endpoint : {config.minio.endpoint}")
    print(f"Bucket         : {config.minio.bucket}")
    print(f"Staging        : {config.paths.staging}")
    print("Config OK")
