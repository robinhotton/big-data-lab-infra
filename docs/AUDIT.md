# Audit — bonnes pratiques & implémentation

Audit de la stack lab **MinIO (S3) + Airflow** avant rigidification.
Lecture par gravité : d'abord ce qui bloque, ensuite la dette.

Date : 2026-10-07 · Portée : `docker-compose.yml`, `scripts/`, `airflow/`, `tests/`, `setup_datasets.py`, `.env.example`.

---

## 1. Synthèse

| | |
| --- | --- |
| État général | Bon pour un lab pédagogique mono-utilisateur local |
| Bloquant | Images MinIO upstream archivées → **corrigé en V1** (voir §2.1) |
| Dette principale | Pas de CI, secrets lab exposés sans restriction réseau, deps installées au démarrage |
| Dette connue | Airflow `2.9.3` (ligne 2.9, CVE), fork `pgsty/minio` gelé |

La stack est volontairement **minimaliste** : pas de Spark, pas de Postgres métier,
pas de cluster. L'audit respecte ce cadrage — il ne s'agit pas de la transformer
en plateforme prod, mais de faire que ce qui est annoncé soit vrai et tienne
avant un TP.

---

## 2. Points forts (à conserver)

Ces choix sont justes et documentés : ne pas les « re-durcir » à l'aveugle.

| Pratique | Où | Pourquoi c'est bon |
| --- | --- | --- |
| Secrets uniquement dans `.env` (gitignoré), jamais dans le YAML | `.env.example`, `docker-compose.yml` | Aucun secret en dur dans git ; `:?` fait échouer le `up` si `.env` manque |
| Images **pinnées** sur tag de release, pas `latest` | `docker-compose.yml` | Reproductibilité d'une session de formation à l'autre |
| Healthchecks + `depends_on: condition:` | `minio`, `postgres`, `airflow-*` | Pas de course : `minio-init` ne démarre que le MinIO healthy |
| One-shots **idempotents** | `scripts/*.sh` | `docker compose up` re-exécutable sans doublon ni erreur |
| Séparation DAG / code métier | `airflow/src/` vs `airflow/dags/` | `airflow/src` testable hors Airflow — bonne pratique à montrer en TP3 |
| Volumes nommés (pas de bind mount) | `volumes:` | Évite les `Permission denied` UID 50000 / hôte, notamment Linux |
| Network nommé `lab-net` | `docker-compose.yml` | Références `docker run --network` stables si le dossier est renommé |
| Remote logging Airflow → MinIO | `AIRFLOW__LOGGING__REMOTE_*` | Logs survivent à une recréation de conteneur |
| SSE-S3 sur le bucket + lifecycle `raw/` 365j | `scripts/minio-init.sh` | Habitudes de bonnes mœurs stockage, gratuites ici |
| Données générées (RNG seedé) plutôt que commitées | `setup_datasets.py` | Évite 242 Mo en git, données comparables entre apprenants |
| `.gitattributes` force `*.sh` en LF | `.gitattributes` | Corrige le bug `set -eu\r` sous busybox (commit `dedab38`) |
| Tests métier hors Docker | `tests/` | Déjà une amorce utile, alignée sur le TP3 |

---

## 3. Anomalies

### A1 — 🔴 Critique · Images MinIO upstream disparues · `docker-compose.yml`

`minio/minio:RELEASE.2024-10-13T13-34-11Z` et `minio/mc:RELEASE.2024-10-02T08-27-28Z`
ne sont **plus téléchargeables** (repo archivé en 2026-02, distribution binaire
coupée) :

```
$ docker manifest inspect minio/minio:RELEASE.2024-10-13T13-34-11Z
denied: requested access to the resource is denied
```

Conséquence : la stack ne démarre plus pour aucun apprenant.

→ **Corrigé en V1** : bascule vers `pgsty/minio` / `pgsty/mc` (fork AGPL
communautaire, drop-in compatible). Voir `docs/HARDENING-ROADMAP.md` pour la
migration V2/V3 vers la ligne maintenue `pgsty/silo`.

### A2 — 🟠 Élevée · Pagination S3 absente · `airflow/src/extract.py`

```python
resp = s3.list_objects_v2(Bucket=cfg.bucket, Prefix=prefix)
keys = [obj["Key"] for obj in resp.get("Contents", []) if ...]
```

`ListObjectsV2` renvoie **1000 objets max** par page. Au-delà, les fichiers
sont silencieusement ignorés → le pipeline perd des données sans erreur.

Le dataset du lab reste sous 1000 clés par préfixe, donc invisible en TP.
Mais c'est un défaut exactement du type « ça marche en cours, ça casse en
production » — et c'est un bon sujet de TP.

→ À corriger en V2 (ou en exercice).

### A3 — 🟡 Moyenne · Connexion Airflow en JSON dans le Compose · `docker-compose.yml`

```yaml
AIRFLOW_CONN_MINIO_DEFAULT: '{"conn_type":"aws",...\"login\":\"${MINIO_ROOT_USER}\"...}'
```

Problèmes :
- guillemets imbriqués + échappements → fragile dès qu'un password contient `"` ou `\` ;
- les credentials finissent en clair dans `docker inspect` et dans les variables
  du process, pas seulement dans `.env`.

→ V2 : passer par un fichier de connexion (monté en volume) ou des `_FILE`
  variants, et un mot de passe Airflow applicatif distinct du root MinIO.

### A4 — 🟡 Moyenne · Ports exposés sur toutes les interfaces · `docker-compose.yml`

`9000`, `9001`, `8080` sont publiés en `0.0.0.0`. Sur un poste de formation en
Wi-Fi d'entreprise / salle, n'importe qui sur le réseau peut tenter `admin/admin`
(services volontairement non durcis).

→ V2 : `127.0.0.1:9000:9000` etc. Suffisant pour Colab local + Jupyter + navigateur.

### A5 — 🟡 Moyenne · Dépendances installées au démarrage · `docker-compose.yml`

```yaml
_PIP_ADDITIONAL_REQUIREMENTS: "boto3==1.34.162 apache-airflow-providers-amazon==8.10.0 pandas==2.2.2"
```

Installé à **chaque premier démarrage** d'un conteneur Airflow : ~30-60 s de
latence en début de TP, dépendance à un index PyPI disponible, et rien ne
garantit la reproducibilité si un pin saute.

Idem dans `scripts/datasets-init.sh` (`pip install` à chaque run du one-shot).

→ V2 : image Airflow custom (`Dockerfile` qui pré-installe les deps), ou
  `requirements.txt` monté + `pip install` au build.

### A6 — 🟡 Moyenne · Aucune CI · (absent)

Rien ne vérifie avant un TP que le repo tourne encore. C'est exactement la
panne qu'on vient de subir : une image a disparu et personne ne l'a su.

→ V2 : GitHub Actions (lint + pytest + smoke test compose). Voir
  `docs/HARDENING-ROADMAP.md`.

### A7 — 🟢 Faible · Credentials en clair dans les defaults · `airflow/src/config.py`

```python
access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
```

Un code métier qui **silence** une config absente avec des identifiants de lab
est un vrai antipattern : en prod, ça exécute un pipeline contre le mauvais
bucket avec les credentials fournis par défaut.

Acceptable ici (lab, creds documentées), mais à retirer dès que le code sort
du lab — fail-fast si la variable est absente.

### A8 — 🟢 Faible · Règles de lifecycle qui s'accumulent · `scripts/minio-init.sh`

`mc ilm add` ajoute une règle à chaque exécution. Sur un volume persistant,
relancer `datasets-init` / recréer le service `minio-init` duplique les règles
(observé : une règle par run).

→ V2 : `mc ilm rule ls | grep` avant ajout, ou `mc ilm rule rm` + re-add, ou
  poser la règle via l'API/`mc ilm rule import` déclaratif.

### A9 — 🟢 Faible · Pins de versions divergents · `requirements.txt` / `docker-compose.yml`

`boto3==1.34.162` est pinné partout, mais `pyarrow` (requis pour le taxi
Parquet) ne l'est que dans `scripts/datasets-init.sh` et pas dans
`_PIP_ADDITIONAL_REQUIREMENTS`. Si un TP lit du Parquet dans Airflow, il
échouera sans que le README ne le dise.

→ V2 : un fichier de deps unique source de vérité.

### A10 — 🟢 Faible · Doc désalignée · `README.md`, `.gitignore`

- le README décrit un staging **Parquet** dans `airflow_data`, alors que le DAG
  `orders_pipeline` passe par **XCom** (200 events/jour) — le commentaire du DAG
  est plus juste que le README ;
- `.gitignore` ignore `.claude`, ce qui peut surprendre selon les conventions ;
- le README mentionne `pytest-airflow` / `moto` qui ne sont pas dans les deps.

→ V2 : relecture doc.

### A11 — ℹ️ Info · Airflow 2.9.3 · `docker-compose.yml`

Ligne 2.9 (2024). Des CVE affectent les versions non patchées d'Airflow et de
ses providers. Décision : **rester sur 2.9.3 pour la V1** (compatibilité des
supports de cours, API `PythonOperator` + `context['ds']` utilisée en TP).

→ V2 : monter en dernière version **2.x** (API compatible), jamais 3.x sans
  refonte des supports.

### A12 — ℹ️ Info · Fork `pgsty/minio` gelé

Le fork choisi en V1 a été renommé `pgsty/silo` le 2026-08-06 ; les artefacts
`pgsty/minio` restent figés sur `RELEASE.2026-08-04T00-00-00Z` et ne recevront
plus de correctifs sous ce nom.

→ C'est une dette **délibérée** (réparer vite pour les apprenants). Migration
  prévue en V2/V3. Voir `docs/HARDENING-ROADMAP.md`.

---

## 4. Ce que l'audit n'a *pas* cherché à corriger

Par choix de cadrage (lab pédagogique local) :

- Pas de HA, pas de multi-nœud, pas de cluster MinIO
- Pas de TLS (usage localhost)
- Pas de gestion de secrets type Vault
- Pas de monitoring / métriques
- Pas de Postgres « métier » — les données vivent dans le data lake

Ajouter ces briques ici nuirait à la lisibilité pédagogique. Si la stack doit
servir hors formation (env d'entreprise, données réelles), ce sont eux les
prochains chantiers — après la V2.
