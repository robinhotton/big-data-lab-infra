#!/bin/sh
# fix-minio-policies.sh
# Applique la policy IAM correcte (raw/ = lecture seule) sur les comptes existants.
# Usage : docker exec mc sh /fix-minio-policies.sh
# Ou : NB_BINOMES=11 MINIO_ENDPOINT=http://host:9000 sh fix-minio-policies.sh

set -e

NB_BINOMES=${NB_BINOMES:-11}
MINIO_ENDPOINT=${MINIO_ENDPOINT:-http://minio:9000}
MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin123}

mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

echo "=== Fix policies IAM — ${NB_BINOMES} binômes (raw/ = lecture seule) ==="

i=1
while [ "$i" -le "$NB_BINOMES" ]; do
  NUM=$(printf "%02d" "$i")
  USER="binome${NUM}"
  BUCKET="data-lake-binome-${NUM}"

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
      "Action": ["s3:*"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}/bronze/*",
        "arn:aws:s3:::${BUCKET}/silver/*",
        "arn:aws:s3:::${BUCKET}/gold/*",
        "arn:aws:s3:::${BUCKET}/quarantine/*"
      ]
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
  rm -f "/tmp/policy-${USER}.json"

  echo "  OK : ${USER} — raw/ lecture seule, cleansed/ RW, curated/ complet"
  i=$((i + 1))
done

echo "=== Done — relancez test_iam.py pour vérifier ==="
