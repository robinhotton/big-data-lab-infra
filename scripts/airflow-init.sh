#!/bin/bash
# airflow-init.sh — initialise la base Airflow et crée l'utilisateur admin (one-shot).
# Exécuté par le service `airflow-init` en root (user: "0:0") pour pouvoir corriger
# les permissions des volumes airflow_data et airflow_logs. Idempotent (le `|| true`
# sur users create évite l'échec si l'utilisateur existe déjà).
set -eu

# Pré-crée les sous-dossiers de staging avec les bonnes permissions (airflow:root
# 775) AVANT le db migrate — sinon ils sont créés en root:root 755 et le pipeline
# + le dag processor (qui tournent sous UID 50000) échouent en PermissionError.
mkdir -p /opt/airflow/data/staging /opt/airflow/data/reports /opt/airflow/logs/scheduler

airflow db migrate

airflow users create \
    --username "$AIRFLOW_ADMIN_USER" \
    --password "$AIRFLOW_ADMIN_PASSWORD" \
    --firstname Admin \
    --lastname Formateur \
    --role Admin \
    --email admin@formation.local || true

# Corrige récursivement les permissions des deux volumes à la fin : db migrate et
# le parsing DAG peuvent créer des sous-dossiers (logs/scheduler/...) en root.
# On repasse en airflow:root 775 pour que webserver/scheduler/dag-processor (UID
# 50000) puissent y écrire.
chown -R 50000:0 /opt/airflow/data /opt/airflow/logs
chmod -R 775 /opt/airflow/data /opt/airflow/logs

echo "✓ Airflow initialisé (base migrée, user admin créé, volumes data+logs corrigés)."
