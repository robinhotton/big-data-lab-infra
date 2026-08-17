"""
setup_datasets.py — Chargement des datasets de formation dans MinIO.

A exécuter par le formateur après `docker compose up -d` (ou via formateur-start.sh).
Idempotent : peut être relancé sans risque, les fichiers existants sont écrasés.

Datasets chargés par défaut :
  TP1  raw/sales/year=2026/month=03/transactions_2026-03-NN.csv  (8 fichiers × 500k lignes)
  TP1  raw/weather/weather_2025.csv                              (365 jours × 7 stations)
  TP2  raw/taxi/yellow_tripdata_sample.parquet                   (130k lignes, synthétique)
  TP2  raw/taxi/yellow_tripdata_2023-01.parquet                  (3M lignes, NYC TLC réel)
  TP3  raw/orders/2026/03/orders_2026-03-DD.json                 (31 fichiers × 200 événements)

Usage :
    python setup_datasets.py
    python setup_datasets.py --endpoint http://[hidora-url]:9000 --nb-binomes 7

Options :
    --endpoint         URL MinIO (défaut : http://localhost:9000)
    --access-key       Access key MinIO (défaut : minioadmin)
    --secret-key       Secret key MinIO (défaut : minioadmin123)
    --prefix-bucket    Préfixe des buckets (défaut : data-lake-binome)
    --nb-binomes       Nombre de binômes (défaut : 7)
    --nb-events        Événements orders par jour (défaut : 200)
    --csv-rows         Lignes par fichier CSV transactions (défaut : 500000)
    --skip-csv         Ne pas charger les CSV TP1
    --skip-taxi        Ne pas charger le Parquet taxi sample
    --skip-taxi-full   Ne pas télécharger le Parquet taxi full (nécessite Internet)
    --skip-orders      Ne pas charger les orders TP3
"""

import argparse
import csv
import io
import json
import random
import uuid
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError


# ── Données de référence ──────────────────────────────────────────────────────

# Orders (TP3)
ORDER_STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "cancelled"]
PRODUCTS       = [f"prod-{i:03d}" for i in range(1, 51)]
USERS          = [f"usr-{i:04d}" for i in range(1, 201)]
PRICES         = [4.99, 9.99, 14.99, 19.99, 29.99, 49.99, 79.99, 99.99, 149.99, 199.99]

# Transactions CSV (TP1)
REGIONS = [
    "Île-de-France", "Auvergne-Rhône-Alpes", "Occitanie",
    "Nouvelle-Aquitaine", "Grand Est", "Hauts-de-France",
    "Pays de la Loire", "Bretagne", "Normandie", "PACA",
]
CSV_STATUSES  = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
CSV_PAYMENTS  = ["card", "card", "card", "bank_transfer", "paypal", "cash"]

# Météo (TP1)
STATIONS   = ["Paris-CDG", "Lyon-Bron", "Marseille-MP", "Toulouse-Blagnac",
              "Bordeaux-Mérignac", "Nantes-Atlantique", "Lille-Lesquin"]
CONDITIONS = ["sunny", "sunny", "cloudy", "rainy", "rainy", "stormy", "snow"]

# NYC Taxi full
TAXI_FULL_URL = (
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2023-01.parquet"
)


# ── TP1 — CSV transactions ────────────────────────────────────────────────────

def generate_csv_transactions(n_rows: int, date_str: str, file_num: int) -> bytes:
    """Génère un CSV transactions pour une date donnée (colonnes : id, date, region, amount, status, payment_method)."""
    rng = random.Random(42 + file_num)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "date", "region", "amount", "status", "payment_method"])
    for i in range(n_rows):
        writer.writerow([
            f"txn-{file_num:02d}{i + 1:07d}",
            date_str,
            rng.choice(REGIONS),
            round(rng.uniform(5.0, 9999.99), 2),
            rng.choice(CSV_STATUSES),
            rng.choice(CSV_PAYMENTS),
        ])
    return buf.getvalue().encode("utf-8")


def generate_csv_weather(n_days: int = 365) -> bytes:
    """Génère un CSV météo journalier (colonnes : date, station, temperature_c, rainfall_mm, wind_kmh, condition)."""
    rng = random.Random(42)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["date", "station", "temperature_c", "rainfall_mm", "wind_kmh", "condition"])
    base_date = datetime(2025, 1, 1)
    for day in range(n_days):
        current_date = (base_date + timedelta(days=day)).strftime("%Y-%m-%d")
        for station in STATIONS:
            writer.writerow([
                current_date,
                station,
                round(rng.gauss(12, 10), 1),
                round(max(0.0, rng.gauss(2, 5)), 1),
                round(rng.uniform(5, 80), 1),
                rng.choice(CONDITIONS),
            ])
    return buf.getvalue().encode("utf-8")


def upload_csv_transactions(s3, bucket: str, n_files: int = 8, rows_per_file: int = 500_000) -> None:
    total_rows = 0
    total_bytes = 0
    for i in range(1, n_files + 1):
        date_str = f"2026-03-{i:02d}"
        data = generate_csv_transactions(rows_per_file, date_str, i)
        key = f"raw/sales/year=2026/month=03/transactions_2026-03-{i:02d}.csv"
        s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="text/csv")
        total_rows += rows_per_file
        total_bytes += len(data)
    print(f"    ✓ raw/sales/year=2026/month=03/  ({n_files} fichiers × {rows_per_file:,} lignes = {total_bytes / 1024 / 1024:.0f} Mo)")


def upload_csv_weather(s3, bucket: str) -> None:
    data = generate_csv_weather()
    key = "raw/weather/weather_2025.csv"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="text/csv")
    print(f"    ✓ {key}  ({len(data) / 1024:.0f} Ko, 365 jours × {len(STATIONS)} stations)")


# ── TP2 — NYC Taxi sample (Parquet synthétique) ───────────────────────────────

def generate_taxi_parquet(n: int = 130_000) -> bytes:
    """Génère un Parquet taxi synthétique avec le schéma NYC TLC."""
    try:
        import pandas as pd
    except ImportError:
        raise SystemExit("pandas requis : pip install pandas pyarrow")

    rng = random.Random(42)
    base = datetime(2023, 1, 1)
    pickups = [base + timedelta(seconds=rng.randint(0, 31 * 24 * 3600)) for _ in range(n)]

    df = pd.DataFrame({
        "tpep_pickup_datetime":  pd.to_datetime(pickups),
        "tpep_dropoff_datetime": pd.to_datetime(
            [p + timedelta(minutes=rng.randint(3, 90)) for p in pickups]
        ),
        "passenger_count": [rng.choice([1, 1, 1, 2, 3, None]) for _ in range(n)],
        "trip_distance":   [round(rng.uniform(0.1, 30.0), 2) for _ in range(n)],
        "fare_amount":     [round(rng.uniform(-2, 120.0), 2) for _ in range(n)],
        "payment_type":    [rng.choice([1, 1, 2, 3, 4]) for _ in range(n)],
        "PULocationID":    [rng.randint(1, 263) for _ in range(n)],
    })

    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def upload_taxi(s3, bucket: str, data: bytes) -> None:
    key = "raw/taxi/yellow_tripdata_sample.parquet"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/octet-stream")
    print(f"    ✓ {key}  ({len(data) / 1024 / 1024:.1f} Mo, ~130k lignes)")


# ── TP2 — NYC Taxi full (réel, téléchargé depuis NYC TLC) ─────────────────────

def download_taxi_full() -> bytes:
    """Télécharge le Parquet NYC Taxi 2023-01 depuis le site NYC TLC (~45 Mo, ~3M lignes)."""
    import urllib.request
    print(f"  Téléchargement NYC Taxi full dataset (~45 Mo)...")
    print(f"  URL : {TAXI_FULL_URL}")
    try:
        with urllib.request.urlopen(TAXI_FULL_URL, timeout=180) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            data = b""
            chunk_size = 1024 * 1024  # 1 Mo
            downloaded = 0
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                data += chunk
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(f"    {downloaded / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} Mo  ({pct:.0f}%)", end="\r")
        print(f"\n  → {len(data) / 1024 / 1024:.1f} Mo téléchargés.")
        return data
    except Exception as exc:
        print(f"\n  AVERTISSEMENT : téléchargement échoué ({exc})")
        print("  Relancez avec une connexion Internet ou ajoutez --skip-taxi-full.")
        return b""


def upload_taxi_full(s3, bucket: str, data: bytes) -> None:
    key = "raw/taxi/yellow_tripdata_2023-01.parquet"
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/octet-stream")
    print(f"    ✓ {key}  ({len(data) / 1024 / 1024:.1f} Mo, ~3M lignes)")


# ── TP3 — Orders e-commerce (JSON Lines) ─────────────────────────────────────

def generate_orders_day(day: datetime, nb_events: int) -> str:
    """Génère nb_events événements pour un jour donné, format JSON Lines."""
    lines = []
    for _ in range(nb_events):
        ts = day.replace(
            hour=random.randint(0, 23),
            minute=random.randint(0, 59),
            second=random.randint(0, 59),
        )
        lines.append(json.dumps({
            "event_id":   str(uuid.uuid4()),
            "timestamp":  ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "user_id":    random.choice(USERS),
            "product_id": random.choice(PRODUCTS),
            "quantity":   random.randint(1, 5),
            "price":      random.choice(PRICES),
            "status":     random.choice(ORDER_STATUSES),
        }))
    return "\n".join(lines)


def upload_orders(s3, bucket: str, nb_events: int = 200,
                  year: int = 2026, month: int = 3) -> None:
    import calendar
    days = calendar.monthrange(year, month)[1]
    uploaded = 0
    for day_num in range(1, days + 1):
        day = datetime(year, month, day_num)
        content = generate_orders_day(day, nb_events)
        key = f"raw/orders/{year}/{month:02d}/orders_{year}-{month:02d}-{day_num:02d}.json"
        try:
            s3.put_object(Bucket=bucket, Key=key,
                          Body=content.encode("utf-8"), ContentType="application/json")
            uploaded += 1
        except Exception as e:
            print(f"    ✗ Erreur jour {day_num:02d} : {e}")
    print(f"    ✓ raw/orders/{year}/{month:02d}/  ({uploaded}/{days} fichiers × {nb_events} événements)")


# ── Utilitaires ───────────────────────────────────────────────────────────────

def wait_for_minio(s3, retries: int = 10, delay: int = 3) -> None:
    import time
    for i in range(retries):
        try:
            s3.list_buckets()
            return
        except Exception:
            print(f"  MinIO pas encore prêt — attente {delay}s... ({i + 1}/{retries})")
            time.sleep(delay)
    raise SystemExit("MinIO inaccessible après plusieurs tentatives. Vérifiez docker compose ps.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Charge les datasets de formation dans MinIO.")
    parser.add_argument("--endpoint",       default="http://localhost:9000")
    parser.add_argument("--access-key",     default="minioadmin")
    parser.add_argument("--secret-key",     default="minioadmin123")
    parser.add_argument("--prefix-bucket",  default="data-lake-binome")
    parser.add_argument("--nb-binomes",     type=int, default=7)
    parser.add_argument("--nb-events",      type=int, default=200,
                        help="Événements orders par jour (défaut 200)")
    parser.add_argument("--csv-rows",       type=int, default=500_000,
                        help="Lignes par fichier CSV transactions (défaut 500 000)")
    parser.add_argument("--skip-csv",       action="store_true",
                        help="Ne pas charger les CSV TP1")
    parser.add_argument("--skip-taxi",      action="store_true",
                        help="Ne pas charger le Parquet taxi sample")
    parser.add_argument("--skip-taxi-full", action="store_true",
                        help="Ne pas télécharger le Parquet taxi full (nécessite Internet)")
    parser.add_argument("--skip-orders",    action="store_true",
                        help="Ne pas charger les orders TP3")
    args = parser.parse_args()

    s3 = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
    )

    print(f"\n=== Setup datasets formation ===")
    print(f"Endpoint  : {args.endpoint}")
    print(f"Binômes   : {args.nb_binomes}  ({args.prefix_bucket}-01 → -{args.nb_binomes:02d})")
    print(f"Datasets  : "
          f"{'CSV(TP1) ' if not args.skip_csv else ''}"
          f"{'Taxi-sample(TP2) ' if not args.skip_taxi else ''}"
          f"{'Taxi-full(TP2) ' if not args.skip_taxi_full else ''}"
          f"{'Orders(TP3)' if not args.skip_orders else ''}")

    print("\nAttente MinIO...")
    wait_for_minio(s3)
    print("MinIO prêt.\n")

    # ── Pré-génération des assets communs à tous les buckets ──────────────────

    taxi_sample_data = None
    if not args.skip_taxi:
        print("Génération Parquet taxi sample (130 000 lignes)...")
        taxi_sample_data = generate_taxi_parquet()
        print(f"  → {len(taxi_sample_data) / 1024 / 1024:.1f} Mo générés.\n")

    taxi_full_data = None
    if not args.skip_taxi_full:
        taxi_full_data = download_taxi_full()
        print()

    # ── Upload par bucket ─────────────────────────────────────────────────────

    buckets = [f"{args.prefix_bucket}-{i:02d}" for i in range(1, args.nb_binomes + 1)]

    for bucket in buckets:
        print(f"[{bucket}]")
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError:
            print(f"  Bucket {bucket} introuvable — vérifiez que minio-init s'est exécuté.")
            continue

        if not args.skip_csv:
            upload_csv_transactions(s3, bucket, n_files=8, rows_per_file=args.csv_rows)
            upload_csv_weather(s3, bucket)

        if taxi_sample_data:
            upload_taxi(s3, bucket, taxi_sample_data)

        if taxi_full_data:
            upload_taxi_full(s3, bucket, taxi_full_data)

        if not args.skip_orders:
            upload_orders(s3, bucket, args.nb_events)

    print("\n=== Datasets chargés. Les apprenants peuvent commencer. ===")
    print(f"MinIO console : {args.endpoint.replace(':9000', ':9001')}  (minioadmin / minioadmin123)")
    print(f"Airflow UI    : {args.endpoint.replace(':9000', ':8080')}  (admin / admin)\n")


if __name__ == "__main__":
    main()
