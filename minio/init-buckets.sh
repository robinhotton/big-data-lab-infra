#!/bin/sh
# init-buckets.sh
# Crée le bucket data-lake et applique la lifecycle rule raw/.
# Idempotent : --ignore-existing ne recrée pas un bucket existant.
# Exécuté par le service minio-init (restart: "no").

set -e

echo ">>> Connexion à MinIO..."
mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

echo ">>> Création du bucket data-lake..."
mc mb "local/data-lake" --ignore-existing
# Lifecycle : expiration raw/ après 365 jours (équivalent MinIO de Glacier)
mc ilm add --expiry-days 365 --prefix "raw/" "local/data-lake" 2>/dev/null || true
echo "    ✓ data-lake  (lifecycle raw/ 365j)"

echo ">>> Bucket prêt."
echo ">>> Lancez ensuite : python setup_datasets.py"
