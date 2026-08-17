#!/bin/bash
# start.sh — Démarre la stack locale (MinIO + Airflow) et charge les datasets.
# A exécuter depuis la racine du dépôt. Pas besoin de sudo.
#
# Usage :
#   bash start.sh
#   bash start.sh --skip-datasets        # ne pas charger les datasets
#   bash start.sh --skip-taxi-full       # sans le dataset NYC Taxi (~45 Mo, Internet requis)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Charger .env (créer depuis .env.example si absent) ────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "[init] .env créé depuis .env.example"
fi
set -a
# shellcheck source=/dev/null
source "$SCRIPT_DIR/.env"
set +a

# ── Arguments CLI ────────────────────────────────────────────────────────────
SKIP_DATASETS=false
SKIP_TAXI_FULL=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --skip-datasets)  SKIP_DATASETS=true ;;
    --skip-taxi-full) SKIP_TAXI_FULL=true ;;
    *) echo "Option inconnue : $1"; exit 1 ;;
  esac
  shift
done

MINIO_INTERNAL="http://localhost:9000"

echo ""
echo "================================================================"
echo "  Lab Big Data — Démarrage de votre environnement"
echo "================================================================"
echo "  Datasets  : $([ "$SKIP_DATASETS" = true ] && echo 'ignorés' || echo 'complets (TP1+TP2+TP3)')"
echo ""

cd "$SCRIPT_DIR"

# ── 1. Services core ─────────────────────────────────────────────────────────
echo "[1/5] Démarrage MinIO + PostgreSQL..."
docker compose up -d minio postgres
echo "      OK"

# ── 2. Bucket + lifecycle ─────────────────────────────────────────────────────
echo "[2/5] Création du bucket data-lake + lifecycle..."
docker compose run --rm minio-init
echo "      OK"

# ── 3. Datasets ───────────────────────────────────────────────────────────────
if [ "$SKIP_DATASETS" = false ]; then
  echo "[3/5] Chargement des datasets (TP1 CSV + TP2 Taxi + TP3 Orders)..."
  SKIP_FULL_FLAG=""
  [ "$SKIP_TAXI_FULL" = true ] && SKIP_FULL_FLAG="--skip-taxi-full"
  python3 "$SCRIPT_DIR/setup_datasets.py" \
    --endpoint "$MINIO_INTERNAL" \
    $SKIP_FULL_FLAG
  echo "      OK"
else
  echo "[3/5] Datasets — ignoré"
fi

# ── 4. Airflow ───────────────────────────────────────────────────────────────
echo "[4/5] Démarrage Airflow..."
docker compose up -d airflow-init

echo "      Attente fin d'initialisation Airflow (db migrate + admin)..."
# Poller l'état de airflow-init jusqu'à exit 0 (ou timeout 120s).
# On ne peut pas juste sleep 30 : au 1er démarrage, _PIP_ADDITIONAL_REQUIREMENTS
# rallonge l'init bien au-delà de 30s.
DEADLINE=$(( $(date +%s) + 120 ))
while true; do
  STATUS=$(docker inspect -f '{{.State.Status}}' lab-airflow-init 2>/dev/null || echo "starting")
  if [ "$STATUS" = "exited" ]; then
    CODE=$(docker inspect -f '{{.State.ExitCode}}' lab-airflow-init 2>/dev/null || echo "1")
    if [ "$CODE" -eq 0 ]; then
      echo "      OK — initialisation terminée"
      break
    else
      echo "      ÉCHEC — airflow-init a quitté avec le code $CODE"
      echo "      Logs : docker compose logs airflow-init"
      exit 1
    fi
  fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    echo "      ÉCHEC — timeout : airflow-init toujours en cours après 120s"
    echo "      Logs : docker compose logs airflow-init"
    exit 1
  fi
  sleep 3
done

docker compose up -d airflow-webserver airflow-scheduler
echo "      OK"

# ── 5. Résumé ─────────────────────────────────────────────────────────────────
echo "[5/5] Prêt."
echo ""
echo "================================================================"
echo "  MinIO API     : http://localhost:9000"
echo "  MinIO Console : http://localhost:9001  (admin: $MINIO_ROOT_USER)"
echo "  Airflow       : http://localhost:8080  (admin / admin)"
echo "  Bucket        : data-lake"
echo "================================================================"
echo ""
