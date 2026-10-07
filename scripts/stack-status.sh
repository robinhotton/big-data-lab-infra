#!/usr/bin/env bash
# stack-status.sh — vue ops de la stack lab (contrôle logs / tracking / état).
#
# Affiche : état des services, erreurs récentes, usage disque des volumes,
# rotation des logs Docker, disponibilité des images épinglées.
#
# Usage :  ./scripts/stack-status.sh
#          STATUS_SECTIONS=svc,err ./scripts/stack-status.sh   # sections ciblées
#          ./scripts/stack-status.sh --offline                 # sans réseau
#
# Conçu pour un formateur qui doit pouvoir « tout contrôler » en une commande.

set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml"
ERR_LINES="${ERR_LINES:-15}"
OFFLINE=0
[ "${1:-}" = "--offline" ] && OFFLINE=1

# Sections à afficher (toutes par défaut)
WANTED="${STATUS_SECTIONS:-svc,err,vols,logs,imgs}"
has_section() { case ",$WANTED," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

echo "════════════════════════════════════════════════════════════"
echo "  LAB STACK STATUS — $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════════════"

# ── 1. État des services ─────────────────────────────────────
section_svc() {
    echo ""
    echo "── Services ─────────────────────────────────────────────"
    # L'en-tête Compose pour ExitCode affiche "<no value>" : on le gère nous-mêmes.
    printf '  %-20s %-10s %-32s %s\n' "SERVICE" "STATE" "STATUS" "EXITCODE"
    $COMPOSE ps -a --format '{{.Service}}|{{.State}}|{{.Status}}|{{.ExitCode}}' \
        | while IFS='|' read -r svc state status exit; do
            printf '  %-20s %-10s %-32s %s\n' "$svc" "$state" "$status" "$exit"
        done
    echo ""
    echo "  (jobs one-shot : ExitCode doit être 0 ; sinon relancer"
    echo "   docker compose up minio-init airflow-init datasets-init)"
}

# ── 2. Erreurs récentes dans les logs ────────────────────────
section_err() {
    echo ""
    echo "── Erreurs récentes (dernières ${ERR_LINES}) ─────────────"
    found=0
    for svc in minio postgres airflow-init airflow-webserver airflow-scheduler; do
        # Filtre le bruit connu : premier `db migrate` (tables Airflow absentes)
        # et les avertissements de résolution pip du démarrage Airflow.
        lines=$($COMPOSE logs --tail 200 "$svc" 2>&1 \
            | grep -E -i 'ERROR|CRITICAL|Traceback|Exception|FATAL|panic|denied|refused' \
            | grep -v -E 'relation ".*" does not exist|relation "ab_user"|pip.s dependency resolver|dependency conflicts' \
            | tail -"$ERR_LINES") || true
        if [ -n "$lines" ]; then
            found=1
            echo "[$svc]"
            echo "$lines" | sed 's/^/  /'
        fi
    done
    if [ "$found" -eq 0 ]; then
        echo "  ✓ aucune erreur (le bruit du premier db migrate est filtré)"
    fi
}

# ── 3. Usage disque des volumes ──────────────────────────────
section_vols() {
    echo ""
    echo "── Volumes (usage disque) ───────────────────────────────"
    # docker system df -v : pas de conteneur, pas de pull → utilisable offline.
    docker system df -v 2>/dev/null | awk '
        /VOLUME NAME/ {p=1; next}
        /Local Volumes space usage/ {p=1; next}
        p && NF==0 {p=0}
        p && $1 ~ /^lab_/ {printf "  %-28s %6s\n", $1, $3}
    ' || echo "  (indisponible)"
}

# ── 4. Rotation des logs Docker ──────────────────────────────
section_logs() {
    echo ""
    echo "── Rotation des logs Docker ─────────────────────────────"
    # `-a` : inclut aussi les jobs one-shot déjà terminés (minio-init…).
    docker ps -a --format '{{.Names}}' | grep -E 'lab-' | while read -r c; do
        driver=$(docker inspect -f '{{.HostConfig.LogConfig.Type}}' "$c" 2>/dev/null || echo "?")
        opts=$(docker inspect -f '{{.HostConfig.LogConfig.Config}}' "$c" 2>/dev/null || echo "{}")
        echo "  $c : $driver $opts"
    done
}

# ── 5. Disponibilité des images épinglées ────────────────────
section_imgs() {
    echo ""
    echo "── Images épinglées (disponibilité) ─────────────────────"
    if [ "$OFFLINE" = "1" ]; then
        echo "  (section ignorée : --offline)"
        return 0
    fi
    failed=0
    # Uniquement les clés `image:` du compose (pas volumes, ports, URLs…).
    for img in $(grep -E '^[[:space:]]+image:' docker-compose.yml | awk '{print $2}' | sort -u); do
        if docker manifest inspect "$img" >/dev/null 2>&1; then
            echo "  ✓ $img"
        else
            echo "  ✗ INTROUVABLE $img  ← la CI doit alerter, vérifier le registry"
            failed=1
        fi
    done
    if [ "$failed" -eq 0 ]; then
        echo "  ✓ toutes les images du compose sont résolubles"
    fi
}

has_section svc  && section_svc
has_section err  && section_err
has_section vols && section_vols
has_section logs && section_logs
has_section imgs && section_imgs

echo ""
echo "════════════════════════════════════════════════════════════"
