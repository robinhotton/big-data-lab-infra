#!/bin/sh
# minio-init.sh — crée le bucket data-lake et sa lifecycle rule (one-shot).
# Exécuté par le service `minio-init` du docker-compose. Idempotent.
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb local/data-lake --ignore-existing
# Chiffrement SSE-S3 activé sur le bucket (clé KMS locale posée en env sur minio).
mc encrypt set sse-s3 local/data-lake

# Lifecycle : expiration après 365 jours (pas de GLACIER/IA).
# Idempotent : on ne pose la règle que si le préfixe n'est pas déjà couvert,
# sinon chaque re-run de minio-init empile un doublon (audit A8).
#
# ATTENTION : l'image `pgsty/mc` n'embarque que `cat`, `tr`, `head` —
# ni grep, ni sed, ni awk. La recherche se fait donc en pur shell
# (parcours ligne à ligne + `case`), et pas avec grep.
ensure_expiry_rule() {
    prefix="$1"; days="$2"
    found=0
    # `mc ilm rule ls` : une règle par ligne, le préfixe y figure.
    while IFS= read -r line; do
        case "$line" in
            *"$prefix"*) found=1; break ;;
        esac
    done <<EOF
$(mc ilm rule ls local/data-lake 2>/dev/null)
EOF
    if [ "$found" -eq 1 ]; then
        echo "  · règle lifecycle déjà présente pour ${prefix} (${days} j)"
    else
        mc ilm add --expiry-days "$days" --prefix "$prefix" local/data-lake
    fi
}
ensure_expiry_rule "raw/" 365
# Les logs de tâches Airflow sont poussés par le remote logging et ne sont
# pas des données de formation : 30 jours suffisent (audit — sans ce règne,
# airflow-logs/ pousse sans limite).
ensure_expiry_rule "airflow-logs/" 30

echo "✓ Bucket data-lake prêt (SSE-S3 + lifecycle raw/ 365 j, airflow-logs/ 30 j)."
