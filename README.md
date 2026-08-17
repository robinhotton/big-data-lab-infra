# Lab Infra — Formation Big Data dans le Cloud

Environnement lab de la formation : **MinIO** (stockage objet S3) + **Airflow** (orchestration), avec chargement automatique des datasets.

Chaque apprenant lance **sa propre stack en local** — un seul bucket `data-lake`, un seul compte admin. Pas de déploiement centralisé.

> Ce dépôt est le volet **infrastructure** de la formation. Les supports de cours, TP et annexes pédagogiques vivent dans le dépôt séparé [`cours-big-data-cloud`](https://github.com/robinhotton/cours-big-data-cloud).

---

## Architecture

La stack tient dans 6 conteneurs Docker et 4 volumes nommés :

```text
                            ┌─────────────────────────────────────┐
                            │            Apprenant                │
                            └───────┬───────────────┬─────────────┘
                        Colab/Jupyter│               │ navigateur
                                    ▼               ▼
   ┌───────────────────────────────────────┐   ┌──────────────┐
   │  MinIO  (lab-minio)                   │   │  Airflow UI   │
   │  S3-compatible — :9000 (API)          │   │  :8080        │
   │                  — :9001 (console)   │   │  webserver +  │
   │  bucket data-lake + KMS (SSE-S3)      │◄──┤  scheduler    │
   │  volume: minio_data                   │   │              │
   └───────────────┬───────────────────────┘   └──────┬───────┘
                   │ lecture/écriture orders        │ métadonnées
                   │   (pipeline Bronze→Gold)      ▼
                   │                          ┌──────────────┐
                   │                          │  Postgres 16  │
                   │                          │  (lab-postgres)│
                   │                          │  volume:       │
                   │                          │  postgres_data │
                   │                          └──────────────┘
                   │
   one-shots:  minio-init     → crée bucket + lifecycle raw/ 365j
              datasets-init   → charge les datasets (profile "datasets")
              airflow-init    → db migrate + user admin (|| true)

   tous les services sur le réseau lab-net
   volumes nommés Airflow : airflow_data (staging Parquet)
                            airflow_logs  (logs)
```

### Services

| Conteneur | Rôle | Port | Persistance |
| --- | --- | --- | --- |
| `lab-minio` | Stockage objet S3-compatible, KMS pour SSE-S3 | `9000` API / `9001` console | `minio_data` |
| `lab-minio-init` | One-shot : crée `data-lake` + lifecycle `raw/` 365j | — | — |
| `lab-datasets-init` | One-shot : charge les datasets via `setup_datasets.py` | — | — |
| `lab-postgres` | Métadonnées Airflow (uniquement) | — | `postgres_data` |
| `lab-airflow-init` | One-shot : `db migrate` + user admin idempotent | — | — |
| `lab-airflow-webserver` | UI Airflow | `8080` | — |
| `lab-airflow-scheduler` | Planificateur (healthcheck `airflow jobs check`) | — | — |

> L'inspection du data lake se fait via la **console web MinIO** (`:9001`, click-to-browse) ou en Python via `boto3`. Pas de service AWS CLI dédié — volontairement, pour garder la stack minimale.

### Ce qu'on n'a pas — et pourquoi

- **Pas de cluster Spark** : les TP Spark tournent sur Colab (12 Go RAM). Le lab ne fait que stockage + orchestration.
- **Pas de LLM local** : Gemini/Mistral via API web ou Colab, jamais en local.
- **Pas de Postgres métier** : les données vivent dans MinIO (Parquet). Postgres ne sert qu'à Airflow.

### Données : pourquoi génératif (et pas un dossier `seed/`)

Les 5 datasets sont **générés à l'exécution** par `setup_datasets.py` (RNG seedé) plutôt que stockés en fichiers statiques dans le dépôt — contrairement au pattern `seed/*.sql` d'autres projets Airflow.

| Dataset | Taille | Statique dans git ? |
| --- | --- | --- |
| `weather_2025.csv` | ~120 Ko | ✅ |
| `yellow_tripdata_sample.parquet` | ~3 Mo | ✅ (limite) |
| `orders_2026-03-*.json` (31 fichiers) | ~1,5 Mo | ✅ |
| **`transactions_2026-03-*.csv`** (8 × 500k) | **~242 Mo** | ❌ |
| **`yellow_tripdata_2023-01.parquet`** (réel NYC) | **~45 Mo** | ❌ |

Pourquoi on génère plutôt que committer :

- **242 Mo en git = clone injuriable.** Chaque apprenant télécharge tout l'historique à chaque clone. Git LFS (quota gratuit 1 Go stockage + 1 Go bandwidth/mois) sature dès quelques sessions.
- **Reproductible et idempotent.** Le RNG est **seedé pour tous les datasets** (CSV, météo, taxi sample et orders) → deux apprenants obtiennent des données identiques (comparables en TP), y compris les `event_id` (UUID déterministes). Rejouer `setup_datasets.py` écrase sans doublon.
- **0 dépendance Internet** pour 4 datasets sur 5. Seul le taxi full (~45 Mo, réel NYC TLC) se télécharge — et il est optionnel (`--skip-taxi-full`).

> Le pattern `seed/` (fichiers statiques injectés au démarrage) marche pour des données réelles et petites (~50 Ko). Ici les volumes et la nature synthétique l'imposent : `setup_datasets.py` est notre **seed programmatique**.

---

## Démarrage rapide

```bash
cp .env.example .env       # une seule fois
docker compose up -d       # démarre tout ET charge les datasets
```

C'est tout. `docker compose up -d` enchaîne automatiquement, via les `depends_on` :

1. Démarrage de **MinIO** + **PostgreSQL** (avec healthchecks)
2. `minio-init` : crée le bucket `data-lake` + lifecycle rule (`raw/` expire après 365 j)
3. `datasets-init` : charge les datasets dans le bucket :
   - `raw/sales/year=2026/month=03/transactions_2026-03-NN.csv` (8 fichiers × 500k lignes ≈ 242 Mo) — TP1
   - `raw/weather/weather_2025.csv` (365 jours × 7 stations) — TP1
   - `raw/taxi/yellow_tripdata_sample.parquet` (~3 Mo, 130k lignes, synthétique) — TP2
   - `raw/taxi/yellow_tripdata_2023-01.parquet` (~45 Mo, 3M lignes, NYC TLC réel) — TP2
   - `raw/orders/2026/03/orders_2026-03-*.json` (31 fichiers × 200 événements) — TP3
4. `airflow-init` : `db migrate` + création du user admin
5. Démarrage **Airflow** (webserver + scheduler)

> **Idempotent** : relancements sans risque. Les fichiers existants sont écrasés,
> le bucket existant est conservé (`--ignore-existing`).
>
> **Internet requis** pour le taxi full (~45 Mo depuis NYC TLC). En cas de connexion
> limitée (Plan B réseau offline) : mettre `SKIP_TAXI_FULL=true` dans `.env` avant le
> premier `up`. Les 4 autres datasets sont générés localement, sans Internet.

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24
- Docker Compose ≥ 2.20

```bash
docker --version && docker compose version
```

> Aucun Python, `pip install` ou dépendance locale n'est requis pour démarrer :
> le chargement des datasets s'exécute dans un conteneur (`datasets-init`) qui
> installe ses propres dépendances.

### Démarrer sans charger les datasets

Pour démarrer uniquement la stack (MinIO + Airflow) sans charger les données
(utile pour réutiliser l'environnement sur d'autres TP) :

```bash
COMPOSE_PROFILES= docker compose up -d        # profile "datasets" désactivé
```

### Rechargement des datasets uniquement

```bash
docker compose up --attach datasets-init      # recharge les datasets (one-shot)

# Ou en exécution directe (depuis la racine, Python local avec les deps) :
python setup_datasets.py --endpoint http://localhost:9000

# Options de rechargement partiel :
python setup_datasets.py --skip-taxi-full          # sans re-télécharger les 45 Mo
python setup_datasets.py --skip-csv --skip-taxi    # orders TP3 uniquement
python setup_datasets.py --csv-rows 100000         # CSV réduits (développement)
```

---

## Services & accès

| Service | URL | Identifiants |
| --- | --- | --- |
| MinIO — console web | <http://localhost:9001> | `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` |
| MinIO — API S3 | <http://localhost:9000> | — |
| Airflow | <http://localhost:8080> | `AIRFLOW_ADMIN_USER` / `AIRFLOW_ADMIN_PASSWORD` |

Avec les valeurs de lab par défaut (`.env.example`) : MinIO `minioadmin` / `minioadmin123`, Airflow `admin` / `admin`.

### Configuration (`.env`)

Toutes les variables sont déclarées dans `.env.example` (à copier en `.env`). Aucun secret n'est hardcodé dans `docker-compose.yml` — un `.env` manquant fait échouer le `up` avec un message explicite.

| Variable | Défaut | Description |
| --- | --- | --- |
| `MINIO_ROOT_USER` | `minioadmin` | Login MinIO (root) |
| `MINIO_ROOT_PASSWORD` | `minioadmin123` | Mot de passe MinIO (root) |
| `MINIO_KMS_SECRET_KEY` | `formation-key:AAA…` | Clé KMS locale (SSE-S3 AES256), factice de lab |
| `POSTGRES_USER` | `airflow` | User de la base Airflow (réseau interne, non exposé) |
| `POSTGRES_PASSWORD` | `airflow` | Mot de passe base Airflow |
| `POSTGRES_DB` | `airflow` | Nom de la base Airflow |
| `AIRFLOW_ADMIN_USER` | `admin` | Login Airflow (UI) |
| `AIRFLOW_ADMIN_PASSWORD` | `admin` | Mot de passe Airflow (UI) |
| `SKIP_TAXI_FULL` | `false` | `true` = skip le téléchargement taxi full (Plan B offline) |
| `COMPOSE_PROFILES` | `datasets` | Profiles actifs ; `datasets` lance le chargement auto |

Le bucket unique est `data-lake`.

> Modifiez `.env` avant le **premier** `docker compose up` — le bucket n'est créé qu'une fois.
> Pour recréer : `docker compose down -v && docker compose up -d`

---

## Le pipeline `orders_pipeline`

Un DAG fonctionnel est fourni : `airflow/dags/orders_pipeline_dag.py` — pipeline **Bronze → Silver → Gold** qui lit les JSON `raw/orders/` dans MinIO, nettoie/agrège, écrit `gold/` de façon idempotente.

Un second DAG d'exemple, `airflow/dags/minio_conn_id_example.py`, illustre l'accès à MinIO via une **connexion Airflow** (`S3Hook` + `conn_id`).

### Architecture du code

Le code métier est **séparé du DAG** dans `airflow/src/` (testable hors Airflow) :

```text
airflow/
├── dags/
│   ├── orders_pipeline_dag.py      ← Bronze→Silver→Gold (appelle src/)
│   └── minio_conn_id_example.py     ← exemple : S3Hook + conn_id
└── src/                            ← code métier (pas d'Airflow dedans)
    ├── config.py                  ← endpoints MinIO + chemins (dataclass)
    ├── extract.py                 ← Bronze : JSON MinIO → Parquet staging
    ├── transform.py                ← Silver : typage, dédup, total_price
    └── load.py                     ← Gold : agrégation CA → MinIO (idempotent)
```

Le DAG n'est qu'une **fine couche d'orchestration** : `from src import extract, transform, load`. Les tâches communiquent via **staging Parquet** (volume `airflow_data`, monté en `/opt/airflow/data`) plutôt que par XCom — adapté aux volumes pandas.

> **Pourquoi `src/` ?** Le code métier est testable indépendamment d'Airflow :
> `python -m airflow.src.extract` fonctionne hors conteneur. C'est la bonne pratique
> (séparation orchestration / métier), utile à montrer en TP3.

### Deux façons d'accéder à MinIO depuis un DAG

Le dépôt illustre les deux approches — l'apprenant choisit selon le TP :

| Approche | DAG | Connexion | Avantage |
| --- | --- | --- | --- |
| **boto3 direct** | `orders_pipeline_dag.py` | client créé dans `src/config.py` | Léger, zéro provider, logique centralisée |
| **Airflow Connection** | `minio_conn_id_example.py` | `S3Hook(conn_id="minio_default")` | Bonne pratique Airflow (UI Connections, secret management) |

La connexion `minio_default` est créée automatiquement au démarrage par la variable
`AIRFLOW_CONN_MINIO_DEFAULT` (déclarée dans `docker-compose.yml`) — aucune config
manuelle dans l'UI n'est nécessaire. Vérifiable dans Airflow → **Admin → Connections**.

### Déclencher le DAG

Les DAGs démarrent **en pause** (`DAGS_ARE_PAUSED_AT_CREATION: "true"`). Dans l'UI :

1. <http://localhost:8080> → onglet **DAGs**
2. Activer le DAG (bouton on/off) puis le déclencher (**Trigger DAG w/ config**)
3. La date logique (`ds`) détermine le fichier lu dans MinIO

> `airflow-init` et `minio-init` apparaissent en `exited` dans `docker compose ps` — c'est normal, ils ne s'exécutent qu'une seule fois au démarrage.
>
> `_PIP_ADDITIONAL_REQUIREMENTS` (boto3, pandas, pyarrow) s'installe au premier
> démarrage des conteneurs Airflow : prévoir ~30-60s supplémentaires la première fois.

---

## Accéder aux données

### Console web MinIO

Le plus simple pour inspecter le data lake en TP : la **console web MinIO**
<http://localhost:9001> (`MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`). On y parcourt
les buckets, téléverse des fichiers, et visualise la lifecycle — sans CLI.

### Colab / Jupyter → MinIO

> Colab ne peut pas accéder à votre `localhost`. Pour connecter un notebook à un
> MinIO local, le notebook doit tourner sur la même machine — utilisez Jupyter :

```bash
pip install jupyter pyspark -q
jupyter notebook
```

Credentials à renseigner dans le notebook :

```python
MINIO_ENDPOINT   = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"
BUCKET           = "data-lake"
```

Test de connexion :

```python
%pip install boto3 -q

import boto3

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
)

response = s3.list_objects_v2(Bucket=BUCKET)
print(f"✓ {len(response.get('Contents', []))} objet(s) dans {BUCKET}")
```

---

## Gestion de la stack

```bash
# Arrêter (données conservées)
docker compose down

# Arrêter + supprimer toutes les données (reset complet)
docker compose down -v

# Logs en temps réel
docker compose logs -f
docker compose logs -f minio
docker compose logs -f airflow-scheduler

# Redémarrer un service
docker compose restart airflow-webserver
```

---

## Tests & lint

Le code métier (`airflow/src/`) est conçu pour être testé **hors Docker et hors
Airflow**. Un squelette de tests est fourni dans `tests/` (amorce du TP3 N3 qui
prévoit des tests pytest).

```bash
pip install -r requirements.txt   # installe aussi pytest + ruff
pytest                            # lance les tests
pytest -k transform               # filtre par nom

ruff check .                      # lint
ruff check --fix .                # corrige les erreurs auto (imports, etc.)
```

> Les tests `transform` nécessitent `pyarrow` (Parquet) — ils sont skipés
> automatiquement si absent. Voir `tests/README.md` pour étendre la suite
> (mock MinIO avec `moto`, valider les DAGs avec `pytest-airflow`).

---

## Structure du dépôt

```text
big-data-lab-infra/
├── docker-compose.yml      ← définition des services (MinIO + Airflow)
├── .env.example            ← template de configuration (11 variables)
├── .env                    ← votre config locale (gitignored)
├── setup_datasets.py       ← chargement des datasets dans MinIO (RNG seedé)
├── requirements.txt        ← dépendances Python (runtime + dev : pytest, ruff)
├── pyproject.toml          ← config ruff (lint) + pytest
├── scripts/                ← entrypoints one-shot montés dans les conteneurs
│   ├── minio-init.sh                  ← crée bucket data-lake + lifecycle
│   ├── datasets-init.sh               ← pip install + setup_datasets.py
│   └── airflow-init.sh                ← db migrate + user admin
├── airflow/
│   ├── dags/               ← DAGs (orchestration uniquement)
│   │   ├── orders_pipeline_dag.py    ← Bronze→Silver→Gold (boto3 direct)
│   │   └── minio_conn_id_example.py  ← exemple S3Hook + conn_id
│   └── src/               ← code métier testable hors Airflow
│       ├── config.py                  ← endpoints MinIO + chemins (dataclass)
│       ├── extract.py                 ← Bronze : JSON MinIO → Parquet
│       ├── transform.py               ← Silver : nettoyage + enrichissement
│       └── load.py                    ← Gold : agrégation → MinIO
└── tests/                  ← squelette de tests pytest (amorce TP3 N3)
    ├── conftest.py                    ← fixtures : vars d'env, staging temporaire
    ├── README.md                      ← comment lancer / étendre les tests
    └── airflow_src/
        ├── test_config.py             ← MinIOConfig lit les env vars
        └── test_transform.py          ← dédup, total_price, filtre status
```

> Staging Parquet et logs Airflow vivent dans des **volumes Docker nommés**
> (`airflow_data`, `airflow_logs`) — pas sur le disque hôte. C'est normal de ne pas
> les voir : ce sont des détails internes entre tâches.
>
> L'ancien modèle multi-utilisateur (déploiement centralisé sur Hidora, N buckets
> par binôme, users SSH/MinIO/Airflow) est conservé dans la branche
> `archive/multi-user-hidora`. La branche `main` est **100 % local Docker**.

---

## Dépannage

### Port déjà utilisé

```bash
lsof -i :9000                    # macOS / Linux
netstat -ano | findstr :9000     # Windows
```

Modifiez le mapping de port dans `docker-compose.yml` (`"9002:9000"` par exemple).

### Airflow inaccessible au démarrage

Attendez que `airflow-init` soit terminé (`exited 0`) avant d'ouvrir <http://localhost:8080> :

```bash
docker compose logs airflow-init
```

Si l'init a échoué, relancez les services Airflow :

```bash
docker compose up -d airflow-webserver airflow-scheduler
```

### DAG `orders_pipeline` non visible dans Airflow

```bash
# Le DAG est dans airflow/dags/ — vérifier qu'il est bien monté
docker compose exec airflow-scheduler airflow dags list | grep orders
# Si absent : attendre 60s (refresh automatique du scheduler)
```

### `datasets-init` échoue ou reste bloqué

Le chargement des datasets se fait dans le conteneur `lab-datasets-init`. S'il
échoue (téléchargement taxi full coupé, MinIO pas prêt) :

```bash
docker compose logs datasets-init       # voir la cause

# Recharger uniquement les datasets (sans relancer toute la stack)
docker compose run --rm datasets-init

# En cas d'échec du téléchargement taxi full : passer en mode offline
# (mettre SKIP_TAXI_FULL=true dans .env, puis)
docker compose run --rm -e SKIP_TAXI_FULL=true datasets-init
```

### Chargement des datasets manuel (hors conteneur)

Si vous préférez charger les datasets depuis votre Python local (avec
`boto3 pandas pyarrow` installés) plutôt que via le conteneur :

```bash
python setup_datasets.py --endpoint http://localhost:9000
```

### Credentials AWS CLI incorrects

Vérifiez que `.env` existe et contient les bonnes valeurs, puis relancez depuis la racine du dépôt.
