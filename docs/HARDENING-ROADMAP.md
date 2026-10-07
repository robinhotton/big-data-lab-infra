# Roadmap — rigidification de la stack (V2 / V3)

Plan de montée en robustesse après l'audit (`docs/AUDIT.md`).
Découpage retenu : **V1** = réparer pour les apprenants, **V2** = garde-fous +
durcissement sur branche dédiée, **V3** = migration de ligne de support MinIO.

> ⚠️ Rien de ce document n'est implémenté en V1. Il sert de feuille de route
> et de justification des arbitrages.

---

## Découpage

| Version | Objet | Branche | Statut |
| --- | --- | --- | --- |
| **V1** | Fix images (`pgsty/minio`) + audit + roadmap | `main` + tag | ✅ fait |
| **V2** | CI, tests, durcissement, montée Airflow 2.x | `v2/hardening` | ⏳ à faire |
| **V3** | Migration `pgsty/minio` → `pgsty/silo`, mise à jour des supports | `v3/silo` | ⏳ à faire |

---

## V2 — branche `v2/hardening` (à rabattre sur `main`)

Chaque item est indépendant et découple en commit séparé.

### V2.1 — CI GitHub Actions *(le plus prioritaire)*

**Problème.** Aucune vérification automatique : une image a disparu et personne
ne s'en est aperçu avant un TP. (audit A6)

**Bénéfice.** Détection avant l'apprenant, pas pendant. Feedback immédiat sur
chaque PR.

**Mise en œuvre** — `.github/workflows/ci.yml` :

```yaml
jobs:
  lint-test:      # ruff check . + pytest
  compose-smoke:  # docker compose config → up → healthchecks → down -v
```

Job `compose-smoke` (le cœur) :
1. `cp .env.example .env`
2. `docker compose config -q` — valide la syntaxe + les variables
3. `COMPOSE_PROFILES= docker compose up -d` — sans datasets (plus rapide)
4. Attendre les healthchecks (`docker compose ps` → `healthy` / `exited 0`)
5. `curl -f http://localhost:9000/minio/health/live` → 200
6. `curl -f http://localhost:8080/health` → 200
7. Vérifier le bucket : `docker compose run --rm minio-init` rejoue l'init
8. `docker compose logs minio | grep Version` — affiche la version effective
9. `docker compose down -v`

**Effort.** 0,5 j. **Risque.** Faible (job purement additionnel).

**Échelle supplémentaire.** Un job `release-check` mensuel (cron) qui tente
`docker pull` des images pinées et ouvre une issue si une image a disparu.
C'est exactement le panneau qu'on aurait voulu avoir.

### V2.2 — Tests manquants *(audit A2)*

**Problème.** Seuls `config` et `transform` sont testés. `extract` et `load` —
qui touchent réellement MinIO — ne le sont pas. La pagination manquante
(`ListObjectsV2` limité à 1000 clés) passe donc inaperçue.

**Mise en œuvre** :
- `tests/airflow_src/test_extract.py` : mocker S3, montrer qu'au-delà de 1000
  clés certains fichiers sont perdus (test rouge) → corriger avec un
  paginateur (`list_objects_v2` avec `ContinuationToken`) → test vert
- `tests/airflow_src/test_load.py` : `aggregate_gold`, idempotence de
  `write_json_to_minio` (clé datée), `write_quarantine` (no-op si vide)
- `tests/test_dag_contract.py` : chaque DAG s'importe, expose le bon `dag_id`
  et ne casse pas au parse (pas besoin d'Airflow complet — structure only)

Deps à ajouter aux dev deps : `moto[s3]`, `pyarrow`.

**Effort.** 1 j. **Risque.** Faible.

### V2.3 — Pin par digest des images

**Problème.** Un tag `RELEASE.*` peut être re-publié ou retiré ; un digest ne
change jamais.

**Mise en œuvre** :
```yaml
image: pgsty/minio@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372
```
avec le tag en commentaire pour la lisibilité. Idem pour `pgsty/mc`, `postgres`,
`apache/airflow`, `python`.

**Effort.** 0,25 j. **Risque.** Faible, mais à réviser à chaque upgrade.

### V2.4 — Montée Airflow 2.x *(audit A11)*

**Problème.** Ligne 2.9 (2024), CVE connues.

**Mise en œuvre** : `apache/airflow:2.10.x` (jamais 3.x — casse l'API des DAGs
du cours et les TP). Vérifier spécifiquement :
- `apache-airflow-providers-amazon` compatible (le `S3Hook` et le remote logging)
- `context["ds"]` et `PythonOperator` toujours fournis
- `airflow db migrate` depuis une base déjà en 2.9

**Effort.** 1 j (dont tests des 2 DAGs du lab). **Risque.** Moyen — c'est le
changement qui a le plus de chances de casser un TP, d'où le fait qu'il soit
en V2 et pas dans le fix V1.

### V2.5 — Moins de privilège MinIO *(audit A3, A4)*

**Problème.** Airflow utilise le compte **root** MinIO, et tout est exposé sur
`0.0.0.0`.

**Mise en œuvre** :
1. `minio-init` crée un user applicatif `airflow-app` (policy read/write sur
   `data-lake`, pas de droits admin) — le pipeline du cours n'a pas besoin de root
2. `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` pointent sur ce user, pas sur root
3. Les ports sont publiés en `127.0.0.1:9000:9000` etc.
4. Le `MINIO_ROOT_*` reste dans `.env`, utilisé uniquement par `minio-init` et la
   console

**Effort.** 0,5 j. **Risque.** Moyen — vérifier que le remote logging et le
`S3Hook` fonctionnent avec une policy non-root.

### V2.6 — Image Airflow custom *(audit A5)*

**Problème.** `_PIP_ADDITIONAL_REQUIREMENTS` installe à chaque démarrage :
latence, dépendance réseau, reproducibilité fragile.

**Mise en œuvre** :
```dockerfile
FROM apache/airflow:2.10.x
COPY requirements-airflow.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-airflow.txt
```
et `_PIP_ADDITIONAL_REQUIREMENTS: ""` dans le compose.

**Effort.** 0,5 j. **Risque.** Faible, mais ajoute une image à builder — à
décider si ça vaut le coup pour un lab (le gain de 30-60 s par apprenant est
réel en salle).

### V2.7 — Nettoyage du code métier *(audit A7, A8, A9)*

- `config.py` : **fail-fast** si `MINIO_ACCESS_KEY`/`MINIO_SECRET_KEY` absentes
  (supprimer les defaults de lab) — le lab continue de passer par le compose
- `scripts/minio-init.sh` : rendre la lifecycle idempotente (`mc ilm rule ls`
  avant ajout)
- Un unique `requirements.txt` source de vérité pour les deps runtime + dev
  (dont `pyarrow`, aujourd'hui manquant côté Airflow)

**Effort.** 0,5 j. **Risque.** Faible.

### V2.8 — Relecture doc *(audit A10)*

- README : aligner la description du passage de données (XCom, pas staging
  Parquet) sur le code réel
- README : indiquer que `moto`/`pyarrow` sont nécessaires pour certains tests
- Décrire la CI et comment la rejouer en local

**Effort.** 0,25 j.

---

## V3 — migration `pgsty/silo`

### V3.1 — Bascule MinIO → Silo

**Problème.** `pgsty/minio` est gelé sur `RELEASE.2026-08-04T00-00-00Z`
(branche archivée depuis le renommage du 2026-08-06). Plus aucun correctif de
sécurité ne sortira sous ce nom.

**Solution.** Migrer vers `pgsty/silo` (même code, ligne maintenue).

| | Aujourd'hui (V1) | V3 |
| --- | --- | --- |
| Image serveur | `pgsty/minio:RELEASE.2026-08-04T00-00-00Z` | `pgsty/silo:RELEASE.2026-09-16T00-00-00Z` |
| Image client | `pgsty/mc:RELEASE.2026-08-04T00-00-00Z` | `pgsty/mc:RELEASE.2026-09-16T00-00-00Z` |
| Binaire | `minio` | `silo` |
| CLI | `mc` | `mcli` (+ symlink `mc`) |
| Env vars | `MINIO_*` | `MINIO_*` **conservées** |
| Healthcheck | `curl /minio/health/live` | `silo healthcheck` (natif) ou `/minio/health/live` |
| Données | layout `.minio.sys` | **compatible**, pas de ré-ingestion |

Points de vigilance relevés dans les release notes Silo :
- **password-policy / `admin:ChangeMyPassword`** : séparation des permissions
  IAM → à vérifier si le lab crée des users (cas V2.5)
- **SN-2026-011** (headers `x-amz-*` non signés) : corrigé sur `main`, **pas**
  dans le dernier Server publié `20260903` → checker la version pinée
- **TLS ML-KEM** : réglage Go par défaut, voir `GODEBUG=tlsmlkem=0` si besoin
  (n'impacte pas un usage localhost sans TLS)

**Effort.** 1 j (dont revue des supports de cours). **Risque.** Moyen — nom du
binaire et CLI changent, donc les commandes copiées dans les annexes du cours
sont à mettre à jour.

### V3.2 — Alignement des supports de cours

Le repo `cours-big-data-cloud` référence probablement `minio/minio` et des
commandes `mc`. Mettre à jour en même temps que V3.1 pour ne pas avoir de
supports en décalage avec la stack.

### V3.3 — (option) Credentials et secrets un peu plus sérieux

Si la stack sert à autre chose qu'une formation :
- générer des `MINIO_ROOT_PASSWORD` aléatoires (le `minioadmin123` de lab est
  assumé, mais à ne jamais exporter)
- un vrai gestionnaire de secrets plutôt que `.env` en clair
- TLS même en local (certificats auto-signés) si les données ne sont pas
  synthétiques

---

## Ordre d'implémentation recommandé (V2)

```
V2.1 CI            ← à faire en premier, elle protège tout le reste
V2.2 Tests         ← en parallèle, fait passer A2 au vert
V2.3 Pin digests   ← 30 min, effet immédiat
V2.7 Nettoyage code ← rapide, réduit la surprise
V2.5 Moins de privilège ← un peu plus de valo pédagogique ("on montre la bonne pratique")
V2.6 Image custom  ← si la latence de démarrage gêne en salle
V2.4 Airflow 2.x   ← le plus risqué, en dernier de V2
V2.8 Doc           ← en continu
```

Puis V3 quand la branche V2 est stabilisée et rabattue.

---

## Hors scope (délibéré)

Voir `docs/AUDIT.md` §4 : HA, TLS, Vault, monitoring, cluster, Postgres métier.
Ce sont des chantiers légitimes pour un usage hors formation, mais ils nuisent
à la lisibilité pédagogique du lab tant que ce cadrage tient.
