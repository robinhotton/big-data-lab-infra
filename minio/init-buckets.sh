#!/bin/sh
# init-buckets.sh
# Crée les buckets de chaque binôme et applique la lifecycle rule raw/.
# Idempotent : --ignore-existing ne recrée pas les buckets existants.
# Exécuté par le service minio-init (restart: "no").

set -e

echo ">>> Connexion à MinIO..."
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

echo ">>> Création de $NB_BINOMES buckets (data-lake-binome-01 à $(printf '%02d' $NB_BINOMES))..."
i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  BUCKET=$(printf "data-lake-binome-%02d" "$i")
  mc mb "local/$BUCKET" --ignore-existing
  # Lifecycle : expiration raw/ après 365 jours (équivalent MinIO de Glacier)
  mc ilm add --expiry-days 365 --prefix "raw/" "local/$BUCKET" 2>/dev/null || true
  echo "    ✓ $BUCKET  (lifecycle raw/ 365j)"
  i=$((i + 1))
done

echo ">>> $NB_BINOMES buckets prêts."
echo ">>> Lancez ensuite : python scripts/setup_datasets.py"
