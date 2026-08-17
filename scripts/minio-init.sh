#!/bin/sh
# minio-init.sh — crée le bucket data-lake et sa lifecycle rule (one-shot).
# Exécuté par le service `minio-init` du docker-compose. Idempotent.
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb local/data-lake --ignore-existing
# Chiffrement SSE-S3 activé sur le bucket (clé KMS locale posée en env sur minio).
mc encrypt set sse-s3 local/data-lake
# Lifecycle : expiration des objets sous raw/ après 365 jours (pas de GLACIER/IA).
mc ilm add --expiry-days 365 --prefix "raw/" local/data-lake

echo "✓ Bucket data-lake prêt (SSE-S3 + lifecycle raw/ → 365 j)."
