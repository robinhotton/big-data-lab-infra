#!/bin/bash
# create-ssh-users.sh
# Crée les utilisateurs SSH Linux par binôme sur le serveur hôte.
# Doit être exécuté en root. Idempotent.
#
# Ce que fait ce script par binôme :
#   - useradd + chpasswd
#   - ~/.aws/credentials  (AWS CLI pré-configuré MinIO)
#   - ~/.bashrc           (aliases s3minio + s3api + message d'accueil)
#   - ~/credentials.txt   (tous les accès en un seul fichier)
#   - ~/dags/             (symlink → airflow/dags/binomeXX/)
#   - ~/work/             (dossier de travail vierge)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Charger .env si présent
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
DAGS_BASE="$ROOT_DIR/airflow/dags"
MINIO_ENDPOINT="http://${HIDORA_HOST}:${MINIO_API_PORT}"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERREUR : ce script requiert les droits root."
  echo "Relancez : sudo bash $0"
  exit 1
fi

echo "[SSH Users] Provisionnement de ${NB_BINOMES} utilisateurs..."

i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  USER="binome${NUM}"
  BUCKET="data-lake-binome-${NUM}"
  HOME_DIR="/home/${USER}"

  # Créer ou mettre à jour l'utilisateur
  if ! id "$USER" &>/dev/null; then
    useradd -m -s /bin/bash "$USER"
  fi
  echo "${USER}:${SSH_PASSWORD}" | chpasswd

  # Dossier DAGs par binôme (volume Docker Airflow monté en ./airflow/dags)
  BINOME_DAGS="${DAGS_BASE}/${USER}"
  mkdir -p "$BINOME_DAGS"
  # Readable by Airflow container (UID 50000) + owned by user
  chown "${USER}:${USER}" "$BINOME_DAGS"
  chmod 755 "$BINOME_DAGS"

  # Symlink ~/dags → dossier Airflow du binôme
  ln -sfn "$BINOME_DAGS" "${HOME_DIR}/dags"
  chown -h "${USER}:${USER}" "${HOME_DIR}/dags"

  # Dossier de travail
  mkdir -p "${HOME_DIR}/work"
  chown "${USER}:${USER}" "${HOME_DIR}/work"

  # AWS CLI credentials (endpoint interne localhost:9000 depuis le nœud)
  mkdir -p "${HOME_DIR}/.aws"
  cat > "${HOME_DIR}/.aws/credentials" << EOF
[default]
aws_access_key_id     = ${USER}
aws_secret_access_key = ${SSH_PASSWORD}
EOF
  cat > "${HOME_DIR}/.aws/config" << EOF
[default]
region = us-east-1
EOF
  chown -R "${USER}:${USER}" "${HOME_DIR}/.aws"
  chmod 600 "${HOME_DIR}/.aws/credentials"

  # .bashrc — aliases + message d'accueil (toujours mis à jour)
  # Supprimer l'ancien bloc Formation Big Data s'il existe
  if grep -q "Formation Big Data" "${HOME_DIR}/.bashrc" 2>/dev/null; then
    sed -i '/# === Formation Big Data ===/,/^$/{ /^$/d; d }' "${HOME_DIR}/.bashrc"
  fi
  cat >> "${HOME_DIR}/.bashrc" << EOF

# === Formation Big Data ===
export BUCKET="${BUCKET}"
alias s3minio='aws s3 --endpoint-url http://localhost:9000'
alias s3api='aws s3api --endpoint-url http://localhost:9000'

echo ""
echo "  Bienvenue ${USER} !"
echo "  Vos credentials sont dans : ~/credentials.txt"
echo "  Test rapide : s3minio ls"
echo ""
EOF

  # ~/credentials.txt
  cat > "${HOME_DIR}/credentials.txt" << EOF
=================================================================
  Credentials Formation Big Data — Binôme ${NUM}
=================================================================

SSH
  Hote     : ${HIDORA_HOST}  port ${SSH_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}

MinIO (stockage objet S3)
  API      : ${MINIO_ENDPOINT}
  Console  : http://${HIDORA_HOST}:${MINIO_CONSOLE_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}
  Bucket   : ${BUCKET}

  Test connexion :
    s3minio ls s3://${BUCKET}/

Airflow (orchestration)
  URL      : http://${HIDORA_HOST}:${AIRFLOW_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}

DAGs Airflow
  Deposez vos DAGs dans ~/dags/ (detectes automatiquement en < 1 min)
  Via SCP depuis votre poste :
    scp -P ${SSH_PORT} mon_dag.py ${USER}@${HIDORA_HOST}:~/dags/

  Ces credentials sont aussi dans votre bucket :
    s3minio cp s3://${BUCKET}/credentials.txt .
=================================================================
EOF
  chown "${USER}:${USER}" "${HOME_DIR}/credentials.txt"
  chmod 640 "${HOME_DIR}/credentials.txt"

  echo "  [ssh] ${USER}  (home: ${HOME_DIR}, dags: ${BINOME_DAGS})"
  i=$((i + 1))
done

echo "[SSH Users] Done — ${NB_BINOMES} users créés."
