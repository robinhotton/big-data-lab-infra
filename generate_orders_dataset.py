"""
Script de génération du dataset e-commerce (TP3).

Génère des événements de commandes JSON simulés pour mars 2026,
répartis en 1 fichier par jour, et les uploade dans MinIO.

Usage :
    python generate_orders_dataset.py \
        --endpoint http://[hidora-url]:9000 \
        --access-key [ACCESS_KEY] \
        --secret-key [SECRET_KEY] \
        --prefix-bucket data-lake-binome  # crée data-lake-binome-01 à -07

Options :
    --endpoint      URL MinIO (défaut : http://localhost:9000)
    --access-key    Access key MinIO
    --secret-key    Secret key MinIO
    --prefix-bucket Préfixe de bucket (le script génère pour -01 à -07)
    --single-bucket Nom exact d'un seul bucket (si fourni, ignore --prefix-bucket)
    --nb-events     Nombre d'événements par jour (défaut : 1000)
    --year          Année des données (défaut : 2026)
    --month         Mois des données (défaut : 3 = mars)
    --dry-run       Génère les fichiers localement sans uploader
"""

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path


# --- Données de référence ---
STATUSES = ["completed", "completed", "completed", "pending", "cancelled", "refunded"]
PRODUCTS = [f"prod-{i:03d}" for i in range(1, 51)]   # 50 produits
USERS    = [f"usr-{i:04d}" for i in range(1, 201)]    # 200 utilisateurs
PRICES   = [4.99, 9.99, 14.99, 19.99, 29.99, 49.99, 79.99, 99.99, 149.99, 199.99]


def generate_event(day: datetime) -> dict:
    """Génère un événement de commande aléatoire pour un jour donné."""
    hour   = random.randint(0, 23)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    ts = day.replace(hour=hour, minute=minute, second=second)

    return {
        "event_id":   str(uuid.uuid4()),
        "timestamp":  ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "user_id":    random.choice(USERS),
        "product_id": random.choice(PRODUCTS),
        "quantity":   random.randint(1, 5),
        "price":      random.choice(PRICES),
        "status":     random.choice(STATUSES),
    }


def generate_day(day: datetime, nb_events: int) -> list[dict]:
    """Génère tous les événements d'un jour."""
    return [generate_event(day) for _ in range(nb_events)]


def upload_to_minio(client, bucket: str, key: str, data: str) -> None:
    """Upload du contenu JSON dans MinIO."""
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data.encode("utf-8"),
        ContentType="application/json",
    )


def generate_for_bucket(bucket: str, client, args) -> None:
    """Génère et uploade les données pour un bucket donné."""
    import calendar
    year  = args.year
    month = args.month
    days_in_month = calendar.monthrange(year, month)[1]

    print(f"\n[{bucket}] Génération de {days_in_month} fichiers ({args.nb_events} événements/jour)...")

    for day_num in range(1, days_in_month + 1):
        day = datetime(year, month, day_num)
        events = generate_day(day, args.nb_events)
        content = "\n".join(json.dumps(e) for e in events)   # JSON Lines

        s3_key = f"raw/orders/{year}/{month:02d}/orders_{year}-{month:02d}-{day_num:02d}.json"

        if args.dry_run:
            out_path = Path(f"./output/{bucket}/{s3_key}")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            print(f"  [dry-run] Écrit : {out_path}")
        else:
            upload_to_minio(client, bucket, s3_key, content)
            print(f"  Uploadé  : s3://{bucket}/{s3_key}  ({len(events)} événements)")

    print(f"[{bucket}] OK")


def main():
    parser = argparse.ArgumentParser(description="Génère le dataset e-commerce pour le TP3.")
    parser.add_argument("--endpoint",      default="http://localhost:9000")
    parser.add_argument("--access-key",    default="minioadmin")
    parser.add_argument("--secret-key",    default="minioadmin")
    parser.add_argument("--prefix-bucket", default="data-lake-binome",
                        help="Préfixe bucket — génère pour -01 à -07")
    parser.add_argument("--single-bucket", default=None,
                        help="Nom exact d'un seul bucket (ignore --prefix-bucket)")
    parser.add_argument("--nb-events",     type=int, default=1000,
                        help="Événements par jour (défaut 1000 = ~31 000 sur mars)")
    parser.add_argument("--year",  type=int, default=2026)
    parser.add_argument("--month", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true",
                        help="Écriture locale uniquement, sans upload MinIO")
    args = parser.parse_args()

    if args.dry_run:
        client = None
        print("Mode dry-run : fichiers écrits localement dans ./output/")
    else:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=args.endpoint,
            aws_access_key_id=args.access_key,
            aws_secret_access_key=args.secret_key,
        )

    if args.single_bucket:
        buckets = [args.single_bucket]
    else:
        buckets = [f"{args.prefix_bucket}-{i:02d}" for i in range(1, 8)]

    for bucket in buckets:
        generate_for_bucket(bucket, client, args)

    print("\nGénération terminée.")
    print(f"Chemin MinIO : raw/orders/{args.year}/{args.month:02d}/orders_*.json")


if __name__ == "__main__":
    main()
