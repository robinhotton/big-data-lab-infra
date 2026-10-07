#!/bin/sh
# datasets-init.sh — charge les datasets de formation dans MinIO (one-shot).
# Exécuté par le service `datasets-init` (profile "datasets"). Idempotent.
set -eu

# Installe les dépendances Python nécessaires à setup_datasets.py.
pip install --quiet --no-cache-dir \
    boto3==1.34.162 pandas==2.2.2 pyarrow==16.1.0

# SKIP_TAXI_FULL=true (Plan B réseau offline) est lu par setup_datasets.py.
python setup_datasets.py --endpoint http://minio:9000 --bucket data-lake
