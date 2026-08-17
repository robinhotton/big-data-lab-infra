#!/bin/bash
# formateur-teardown.sh
# Supprime complètement la stack : containers, volumes, users SSH, DAGs, credentials.
# A exécuter depuis la RACINE du dépôt en root (sudo requis pour les users SSH).
#
# Usage :
#   sudo bash formateur-teardown.sh
#   sudo bash formateur-teardown.sh --force          # pas de confirmation
#   sudo bash formateur-teardown.sh --skip-users     # garder les users SSH
#   sudo bash formateur-teardown.sh --skip-volumes   # garder les données MinIO/Postgres

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Charger .env ───────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/.env"
  set +a
fi

NB_BINOMES=${NB_BINOMES:-8}

# ── Arguments CLI ──────────────────────────────────────────────────────────────
FORCE=false
SKIP_USERS=false
SKIP_VOLUMES=false

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --force)        FORCE=true ;;
    --skip-users)   SKIP_USERS=true ;;
    --skip-volumes) SKIP_VOLUMES=true ;;
    *) echo "Option inconnue : $1"; exit 1 ;;
  esac
  shift
done

# ── Résumé et confirmation ─────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo "  Formation Big Data — TEARDOWN"
echo "================================================================"
echo "  Binômes   : ${NB_BINOMES}"
echo "  Users SSH : $([ "$SKIP_USERS" = true ] && echo 'conservés' || echo 'SUPPRIMÉS (userdel -r)')"
echo "  Volumes   : $([ "$SKIP_VOLUMES" = true ] && echo 'conservés' || echo 'SUPPRIMÉS (MinIO data + Postgres)')"
echo "  DAGs      : supprimés (airflow/dags/binome*/)"
echo "  Containers: arrêtés et supprimés"
echo "================================================================"
echo ""

if [ "$FORCE" = false ]; then
  read -r -p "Confirmer la suppression complète ? [oui/N] " CONFIRM
  if [ "$CONFIRM" != "oui" ]; then
    echo "Annulé."
    exit 0
  fi
fi

cd "$SCRIPT_DIR"

# ── 1. Arrêt et suppression des containers ────────────────────────────────────
echo "[1/4] Arrêt et suppression des containers..."
if [ "$SKIP_VOLUMES" = true ]; then
  docker compose down --remove-orphans
else
  docker compose down --volumes --remove-orphans
fi
echo "      OK"

# ── 2. Users SSH ──────────────────────────────────────────────────────────────
if [ "$SKIP_USERS" = false ]; then
  echo "[2/4] Suppression des users SSH..."
  if [ "$(id -u)" -ne 0 ]; then
    echo "      AVERTISSEMENT : non-root — users SSH non supprimés."
    echo "      Relancez : sudo bash formateur-teardown.sh"
  else
    i=1
    while [ "$i" -le "$NB_BINOMES" ]; do
      NUM=$(printf "%02d" "$i")
      USER="binome${NUM}"
      if id "$USER" &>/dev/null; then
        userdel -r "$USER" 2>/dev/null || true
        echo "      [ssh] ${USER} supprimé"
      fi
      i=$((i + 1))
    done
    echo "      OK"
  fi
else
  echo "[2/4] Users SSH — conservés"
fi

# ── 3. Dossiers DAGs par binôme ───────────────────────────────────────────────
echo "[3/4] Suppression des dossiers DAGs par binôme..."
DAGS_BASE="$SCRIPT_DIR/airflow/dags"
i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  BINOME_DAGS="${DAGS_BASE}/binome${NUM}"
  if [ -d "$BINOME_DAGS" ]; then
    rm -rf "$BINOME_DAGS"
    echo "      Supprimé : $BINOME_DAGS"
  fi
  i=$((i + 1))
done
echo "      OK"

# ── 4. Credentials CSV ────────────────────────────────────────────────────────
echo "[4/4] Suppression de credentials.csv..."
if [ -f "$SCRIPT_DIR/credentials.csv" ]; then
  rm -f "$SCRIPT_DIR/credentials.csv"
  echo "      OK"
else
  echo "      Absent — rien à faire"
fi

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo "  Teardown terminé."
echo ""
echo "  Pour repartir de zéro :"
echo "    sudo bash formateur-start.sh"
echo "================================================================"
echo ""
