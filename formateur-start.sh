#!/bin/bash
# formateur-start.sh
# Point d'entrée unique — démarre la stack et provisionne l'environnement complet.
# A exécuter depuis la RACINE du dépôt en root (sudo requis pour les users SSH).
#
# Usage :
#   sudo bash formateur-start.sh
#   sudo bash formateur-start.sh --nb-binomes 6
#   sudo bash formateur-start.sh --skip-datasets --skip-users

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETUP_DIR="$SCRIPT_DIR/setup"

# ── Charger .env (créer depuis .env.example si absent) ────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "[init] .env créé depuis .env.example — vérifiez HIDORA_HOST et NB_BINOMES"
fi
set -a
# shellcheck source=/dev/null
source "$SCRIPT_DIR/.env"
set +a

# ── Arguments CLI (surcharge .env) ────────────────────────────────────────────
SKIP_DATASETS=false
SKIP_USERS=false
SKIP_TAXI_FULL=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --nb-binomes)     NB_BINOMES="$2";   shift ;;
    --skip-datasets)  SKIP_DATASETS=true ;;
    --skip-users)     SKIP_USERS=true ;;
    --skip-taxi-full) SKIP_TAXI_FULL=true ;;
    *) echo "Option inconnue : $1"; exit 1 ;;
  esac
  shift
done

MINIO_INTERNAL="http://localhost:9000"

echo ""
echo "================================================================"
echo "  Formation Big Data — Provisionnement de l'environnement"
echo "================================================================"
echo "  Hôte      : ${HIDORA_HOST:-localhost}"
echo "  Binômes   : ${NB_BINOMES}"
echo "  Datasets  : $([ "$SKIP_DATASETS" = true ] && echo 'ignorés' || echo 'complets (TP1+TP2+TP3)')"
echo "  Users     : $([ "$SKIP_USERS" = true ] && echo 'ignorés' || echo 'SSH + MinIO + Airflow')"
echo ""

cd "$SCRIPT_DIR"

# ── 0. AWS CLI (requis par les aliases s3minio/s3api dans ~/.bashrc des binômes) ─
if ! command -v aws &>/dev/null; then
  echo "[0/7] Installation AWS CLI via pip3..."
  pip3 install --quiet awscli
  echo "      OK — $(aws --version)"
else
  echo "[0/7] AWS CLI déjà présent — $(aws --version)"
fi

# ── 1. Services core ──────────────────────────────────────────────────────────
echo "[1/7] Démarrage MinIO + PostgreSQL..."
NB_BINOMES=$NB_BINOMES docker compose up -d minio postgres
echo "      OK"

# ── 2. Buckets + lifecycle ────────────────────────────────────────────────────
echo "[2/7] Création des buckets + lifecycle..."
NB_BINOMES=$NB_BINOMES docker compose run --rm minio-init
echo "      OK"

# ── 3. Datasets ───────────────────────────────────────────────────────────────
if [ "$SKIP_DATASETS" = false ]; then
  echo "[3/7] Chargement des datasets (TP1 CSV + TP2 Taxi + TP3 Orders)..."
  SKIP_FULL_FLAG=""
  [ "$SKIP_TAXI_FULL" = true ] && SKIP_FULL_FLAG="--skip-taxi-full"
  python3 "$SCRIPT_DIR/setup_datasets.py" \
    --endpoint     "$MINIO_INTERNAL" \
    --nb-binomes   "$NB_BINOMES" \
    $SKIP_FULL_FLAG
  echo "      OK"
else
  echo "[3/7] Datasets — ignoré"
fi

# ── 4. Utilisateurs MinIO (IAM) ───────────────────────────────────────────────
if [ "$SKIP_USERS" = false ]; then
  echo "[4/7] Création des utilisateurs MinIO..."
  docker run --rm \
    --network lab-net \
    -v "$SETUP_DIR:/setup:ro" \
    -e MINIO_ROOT_USER="$MINIO_ROOT_USER" \
    -e MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
    -e NB_BINOMES="$NB_BINOMES" \
    -e SSH_PASSWORD="$SSH_PASSWORD" \
    -e HIDORA_HOST="${HIDORA_HOST:-localhost}" \
    -e MINIO_API_PORT="${MINIO_API_PORT:-9000}" \
    -e MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}" \
    -e SSH_PORT="${SSH_PORT:-22}" \
    -e AIRFLOW_PORT="${AIRFLOW_PORT:-8080}" \
    --entrypoint /bin/sh \
    minio/mc /setup/create-minio-users.sh
  echo "      OK"
else
  echo "[4/7] Utilisateurs MinIO — ignoré"
fi

# ── 5. Utilisateurs SSH ───────────────────────────────────────────────────────
if [ "$SKIP_USERS" = false ]; then
  echo "[5/7] Création des utilisateurs SSH..."
  if [ "$(id -u)" -eq 0 ]; then
    bash "$SETUP_DIR/create-ssh-users.sh"
  else
    echo "      AVERTISSEMENT : non-root — users SSH non créés."
    echo "      Relancez : sudo bash setup/create-ssh-users.sh"
  fi
else
  echo "[5/7] Utilisateurs SSH — ignoré"
fi

# ── 6. Airflow ────────────────────────────────────────────────────────────────
echo "[6/7] Démarrage Airflow..."
docker compose up -d airflow-init
echo "      Attente initialisation (30s)..."
sleep 30
docker compose up -d airflow-webserver airflow-scheduler

if [ "$SKIP_USERS" = false ]; then
  echo "      Création des utilisateurs Airflow..."
  bash "$SETUP_DIR/create-airflow-users.sh"
fi
echo "      OK"

# ── 7. Export credentials ─────────────────────────────────────────────────────
echo "[7/7] Export credentials..."
bash "$SETUP_DIR/export-credentials.sh"
echo "      OK"

# ── Résumé ────────────────────────────────────────────────────────────────────
H="${HIDORA_HOST:-localhost}"
echo ""
echo "================================================================"
echo "  Stack prête."
echo ""
echo "  MinIO API     : http://${H}:${MINIO_API_PORT:-9000}"
echo "  MinIO Console : http://${H}:${MINIO_CONSOLE_PORT:-9001}  (admin: $MINIO_ROOT_USER)"
echo "  Airflow       : http://${H}:${AIRFLOW_PORT:-8080}  (admin / admin)"
echo "  SSH binômes   : ${H}  port ${SSH_PORT:-22}  (binome01..${NB_BINOMES} / $SSH_PASSWORD)"
echo ""
echo "  Credentials   : credentials.csv"
echo "================================================================"
echo ""
