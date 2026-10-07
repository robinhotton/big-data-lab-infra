#!/bin/bash
# smoke-test.sh — vérifie que la stack lab démarre et répond.
#
# Utilisé par la CI (`.github/workflows/ci.yml`) et rejouable en local :
#   ./scripts/smoke-test.sh
#
# La stack tourne en ISOLATION (override `docker-compose.smoke.yml`) :
# pas de port publié sur l'hôte, donc un lab déjà lancé n'est pas perturbé
# et le smoke test peut tourner en parallèle. Les checks de santé se font
# depuis l'intérieur des conteneurs.
#
# Profil "datasets" désactivé : rapide, sans téléchargement, suffisant pour
# valider les images, les healthchecks et le contrat d'initialisation.
set -euo pipefail

cd "$(dirname "$0")/.."

STACK="${SMOKE_STACK:-lab-smoke}"   # nom de projet Compose isolé
WAIT_SECS="${SMOKE_WAIT_SECS:-300}"

compose() {
    docker compose -p "$STACK" --env-file .env -f docker-compose.yml -f docker-compose.smoke.yml "$@"
}

# Code de sortie du smoke test, préservé à travers le trap de nettoyage.
EXIT_CODE=0

cleanup() {
    echo ""
    echo "─── docker compose ps ────────────────────────────────────────"
    compose ps 2>/dev/null || true
    echo "─── logs (extrait) ───────────────────────────────────────────"
    compose logs --tail 20 2>/dev/null || true
    echo "──────────────────────────────────────────────────────────────"
    compose down -v --remove-orphans >/dev/null 2>&1 || true
    exit "$EXIT_CODE"
}
trap cleanup EXIT

echo "▶ Smoke test — projet Compose : $STACK (ports non publiés, lab préservé)"

# .env requis par docker-compose.yml (les vars `:?` échouent sinon)
[ -f .env ] || cp .env.example .env

echo "▶ Validation de la syntaxe Compose"
compose config -q
echo "  ✓ docker compose config"

echo "▶ Démarrage de la stack (sans datasets)"
# Pas de `--wait` : Compose le traite comme un échec quand un one-shot
# (`minio-init`) sort proprement en exit 0. On démarre, puis on attend
# explicitement que les services long-running soient healthy.
if ! COMPOSE_PROFILES= compose up -d; then
    echo "  ✗ docker compose up a échoué"
    EXIT_CODE=1
    exit 1
fi
echo "  ✓ services démarrés"

echo "▶ Attente des healthchecks (services long-running)"
wait_healthy() {
    local service="$1" waited=0
    while [ "$waited" -lt "$WAIT_SECS" ]; do
        local status
        status=$(compose ps --format '{{.Health}}' "$service" 2>/dev/null | head -1)
        case "$status" in
            healthy) echo "  ✓ $service healthy (${waited}s)"; return 0 ;;
            unhealthy) echo "  ✗ $service unhealthy"; return 1 ;;
        esac
        sleep 5
        waited=$((waited + 5))
    done
    echo "  ✗ timeout : $service toujours '$status' après ${WAIT_SECS}s"
    return 1
}
fail=0
for svc in minio postgres airflow-webserver airflow-scheduler; do
    wait_healthy "$svc" || fail=1
done

# Les one-shots doivent être terminés avec succès (exit 0).
# `-a` est indispensable : `ps` sans `-a` masque les conteneurs exited.
for svc in minio-init airflow-init; do
    exit_code=$(compose ps -a --format '{{.ExitCode}}' "$svc" 2>/dev/null | head -1)
    if [ "$exit_code" = "0" ]; then
        echo "  ✓ $svc terminé (exit 0)"
    else
        echo "  ✗ $svc exit=$exit_code (attendu 0)"
        compose logs "$svc" 2>&1 | tail -8 | sed 's/^/     /'
        fail=1
    fi
done

check_in_container() {
    local label="$1" service="$2" url="$3"
    local code
    code=$(compose exec -T "$service" curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" || echo "000")
    if [ "$code" = "200" ]; then
        echo "  ✓ $label → $code"
    else
        echo "  ✗ $label → $code (attendu 200)"
        fail=1
    fi
}
check_in_container "MinIO   /minio/health/live" minio   "http://localhost:9000/minio/health/live"
check_in_container "Airflow /health"            airflow-webserver "http://localhost:8080/health"

echo "▶ Contrat d'initialisation (bucket + SSE-S3 + lifecycle)"
# `minio-init` est un one-shot déjà terminé : on le rejoue pour valider l'idempotence.
if out=$(compose run --rm --no-deps minio-init 2>&1); then
    echo "$out" | tail -3 | sed 's/^/  /'
    echo "  ✓ minio-init rejouable (idempotent)"
else
    echo "$out" | tail -15 | sed 's/^/  /'
    echo "  ✗ minio-init en échec"
    fail=1
fi

echo "▶ Bucket présent et chiffré"
buckets=$(compose exec -T minio sh -c \
    'mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc ls local' 2>/dev/null || true)
if echo "$buckets" | grep -q "data-lake"; then
    echo "  ✓ bucket data-lake présent"
else
    echo "  ✗ bucket data-lake introuvable"
    echo "$buckets" | sed 's/^/     /'
    fail=1
fi

echo "▶ SSE-S3 actif sur le bucket"
enc=$(compose exec -T minio sh -c \
    'mc alias set local http://localhost:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc encrypt info local/data-lake' 2>/dev/null || true)
if echo "$enc" | grep -qi "sse-s3"; then
    echo "  ✓ chiffrement SSE-S3 actif"
else
    echo "  ✗ SSE-S3 non actif"
    echo "$enc" | sed 's/^/     /'
    fail=1
fi

echo "▶ Version effective de MinIO"
compose logs minio 2>&1 | grep -i "Version:" | head -1 | sed 's/^/  /' || true

echo ""
if [ "$fail" -eq 0 ]; then
    echo "✅ Smoke test OK"
    EXIT_CODE=0
    exit 0
fi
echo "❌ Smoke test en échec"
EXIT_CODE=1
exit 1
