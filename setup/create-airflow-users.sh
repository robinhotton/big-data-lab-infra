#!/bin/bash
# create-airflow-users.sh
# Crée les utilisateurs Airflow (rôle Viewer) par binôme.
# Airflow doit être démarré. Idempotent.

set -e

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

echo "[Airflow Users] Création de ${NB_BINOMES} utilisateurs (rôle Viewer)..."

cd "$ROOT_DIR"

i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  USER="binome${NUM}"

  # Supprimer si existe (idempotent) puis recréer
  docker compose exec -T airflow-webserver \
    airflow users delete --username "$USER" 2>/dev/null || true

  docker compose exec -T airflow-webserver \
    airflow users create \
      --username  "$USER" \
      --firstname "Binôme" \
      --lastname  "$NUM" \
      --role      Viewer \
      --email     "${USER}@formation.local" \
      --password  "$SSH_PASSWORD" 2>/dev/null || true

  echo "  [airflow] ${USER} : Viewer"
  i=$((i + 1))
done

echo "[Airflow Users] Done."
