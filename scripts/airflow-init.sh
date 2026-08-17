#!/bin/bash
# airflow-init.sh — initialise la base Airflow et crée l'utilisateur admin (one-shot).
# Exécuté par le service `airflow-init`. Idempotent (le `|| true` sur users create
# évite l'échec si l'utilisateur existe déjà).
set -eu

airflow db migrate

airflow users create \
    --username "$AIRFLOW_ADMIN_USER" \
    --password "$AIRFLOW_ADMIN_PASSWORD" \
    --firstname Admin \
    --lastname Formateur \
    --role Admin \
    --email admin@formation.local || true

echo "✓ Airflow initialisé (base migrée, user admin créé)."
