#!/bin/bash
# export-credentials.sh
# Génère credentials.csv (gitignored) à la racine du dépôt — à distribuer par le formateur.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

NB_BINOMES=${NB_BINOMES:-8}
SSH_PASSWORD=${SSH_PASSWORD:-Diginamic34_}
HIDORA_HOST=${HIDORA_HOST:-localhost}
SSH_PORT=${SSH_PORT:-22}
MINIO_API_PORT=${MINIO_API_PORT:-9000}
MINIO_CONSOLE_PORT=${MINIO_CONSOLE_PORT:-9001}
AIRFLOW_PORT=${AIRFLOW_PORT:-8080}

OUTPUT="$ROOT_DIR/credentials.csv"

echo "binome,ssh_host,ssh_port,user,password,bucket,minio_api,minio_console,airflow" \
  > "$OUTPUT"

i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  USER="binome${NUM}"
  echo "${NUM},${HIDORA_HOST},${SSH_PORT},${USER},${SSH_PASSWORD},data-lake-binome-${NUM},http://${HIDORA_HOST}:${MINIO_API_PORT},http://${HIDORA_HOST}:${MINIO_CONSOLE_PORT},http://${HIDORA_HOST}:${AIRFLOW_PORT}" \
    >> "$OUTPUT"
  i=$((i + 1))
done

echo "  [export] credentials.csv → $OUTPUT"
