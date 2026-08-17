#!/bin/sh
# create-minio-users.sh
# Crée les utilisateurs MinIO + policies IAM par binôme.
# Tourne dans le container minio/mc — appelé par formateur-start.sh.
# Idempotent : peut être relancé sans risque.

set -e

NB_BINOMES=${NB_BINOMES:-8}
SSH_PASSWORD=${SSH_PASSWORD:-Diginamic34_}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin123}
HIDORA_HOST=${HIDORA_HOST:-localhost}
MINIO_API_PORT=${MINIO_API_PORT:-9000}
MINIO_CONSOLE_PORT=${MINIO_CONSOLE_PORT:-9001}
SSH_PORT=${SSH_PORT:-22}
AIRFLOW_PORT=${AIRFLOW_PORT:-8080}

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

# Bucket partagé (lecture seule pour tous les binômes)
mc mb local/data-lake-shared --ignore-existing
echo "  [minio] data-lake-shared : OK"

i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  USER="binome${NUM}"
  BUCKET="data-lake-binome-${NUM}"

  # Créer l'utilisateur (idempotent : reset password si existe déjà)
  mc admin user add local "$USER" "$SSH_PASSWORD" 2>/dev/null || true
  mc admin user enable local "$USER" 2>/dev/null || true

  # Policy IAM TP1 :
  #   - raw/*       : lecture seule (GetObject) — écriture refusée → exercice IAM
  #   - cleansed/*  : écriture + lecture (PutObject, GetObject, DeleteObject)
  #   - curated/*   : accès complet
  #   - bucket root : ListBucket + opérations lifecycle/chiffrement (exercices N2)
  #   - shared      : lecture seule
  cat > "/tmp/policy-${USER}.json" << POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration"
      ],
      "Resource": "arn:aws:s3:::${BUCKET}"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:HeadObject"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}/raw/*",
        "arn:aws:s3:::${BUCKET}/credentials.txt"
      ]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject", "s3:HeadObject"],
      "Resource": "arn:aws:s3:::${BUCKET}/cleansed/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": "arn:aws:s3:::${BUCKET}/curated/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": [
        "arn:aws:s3:::data-lake-shared",
        "arn:aws:s3:::data-lake-shared/*"
      ]
    }
  ]
}
POLICY

  mc admin policy create local "policy-${USER}" "/tmp/policy-${USER}.json" 2>/dev/null || \
    mc admin policy update local "policy-${USER}" "/tmp/policy-${USER}.json" 2>/dev/null || true
  mc admin policy attach local "policy-${USER}" --user "$USER" 2>/dev/null || true

  # Déposer credentials.txt dans le bucket (exercice de découverte TP1)
  cat > "/tmp/credentials-${USER}.txt" << CREDS
=== Credentials Formation Big Data — Binôme ${NUM} ===

SSH
  Hôte     : ${HIDORA_HOST}  port ${SSH_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}

MinIO (stockage objet S3)
  API      : http://${HIDORA_HOST}:${MINIO_API_PORT}
  Console  : http://${HIDORA_HOST}:${MINIO_CONSOLE_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}
  Bucket   : ${BUCKET}

Airflow (orchestration)
  URL      : http://${HIDORA_HOST}:${AIRFLOW_PORT}
  User     : ${USER}
  Password : ${SSH_PASSWORD}

DAGs Airflow
  Deposez vos fichiers dans ~/dags/ via SCP :
  scp -P ${SSH_PORT} mon_dag.py ${USER}@${HIDORA_HOST}:~/dags/
  Airflow detecte les nouveaux DAGs en < 1 min.
CREDS

  mc cp "/tmp/credentials-${USER}.txt" "local/${BUCKET}/credentials.txt" 2>/dev/null || true
  rm -f "/tmp/policy-${USER}.json" "/tmp/credentials-${USER}.txt"

  echo "  [minio] ${USER} : RO raw/ + RW cleansed/ + full curated/ (sans DeleteBucket) + RO shared"
  i=$((i + 1))
done

echo "  [minio] Done — ${NB_BINOMES} users + bucket shared"
