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
   one-shots:  minio-init  → crée bucket + lifecycle raw/ 365j
              airflow-init → db migrate + user admin (|| true)

   volumes nommés Airflow : airflow_data (staging Parquet)
                            airflow_logs  (logs)
```

### Services

| Conteneur | Rôle | Port | Persistance |
| --- | --- | --- | --- |
| `lab-minio` | Stockage objet S3-compatible, KMS pour SSE-S3 | `9000` API / `9001` console | `minio_data` |
| `lab-minio-init` | One-shot : crée `data-lake` + lifecycle `raw/` 365j | — | — |
| `lab-postgres` | Métadonnées Airflow (uniquement) | — | `postgres_data` |
| `lab-airflow-init` | One-shot : `db migrate` + user admin idempotent | — | — |
| `lab-airflow-webserver` | UI Airflow | `8080` | — |
| `lab-airflow-scheduler` | Planificateur (healthcheck `airflow jobs check`) | — | — |
| `awscli` *(à la demande)* | CLI S3 via `docker compose run` | — | bind `./data` |

### Ce qu'on n'a pas — et pourquoi

- **Pas de cluster Spark** : les TP Spark tournent sur Colab (12 Go RAM). Le lab ne fait que stockage + orchestration.
- **Pas de LLM local** : Gemini/Mistral via API web ou Colab, jamais en local.
- **Pas de Postgres métier** : les données vivent dans MinIO (Parquet). Postgres ne sert qu'à Airflow.

---

## Démarrage rapide

```bash
# Depuis la racine du dépôt — démarre tout et charge les datasets
bash start.sh

# Sans le dataset NYC Taxi (~45 Mo, utile si connexion limitée)
bash start.sh --skip-taxi-full
```

`start.sh` enchaîne automatiquement :

1. Création du `.env` depuis `.env.example` (si absent)
2. Démarrage de MinIO + PostgreSQL
3. Création du bucket `data-lake` avec lifecycle rule (`raw/` expire après 365 j)
4. Chargement des datasets dans le bucket :
   - `raw/sales/year=2026/month=03/transactions_2026-03-NN.csv` (8 fichiers × 500k lignes ≈ 242 Mo) — TP1
   - `raw/weather/weather_2025.csv` (365 jours × 7 stations) — TP1
   - `raw/taxi/yellow_tripdata_sample.parquet` (~3 Mo, 130k lignes, synthétique) — TP2
   - `raw/taxi/yellow_tripdata_2023-01.parquet` (~45 Mo, 3M lignes, NYC TLC réel) — TP2
   - `raw/orders/2026/03/orders_2026-03-*.json` (31 fichiers × 200 événements) — TP3
5. Démarrage Airflow (webserver + scheduler)

> **Idempotent** : relancements sans risque. Les fichiers existants sont écrasés,
> le bucket existant est conservé (`--ignore-existing`).
>
> **Internet requis** pour le taxi full (~45 Mo depuis NYC TLC). Ajoutez `--skip-taxi-full` si la connexion est limitée.

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24
- Docker Compose ≥ 2.20
- Python 3 avec `boto3 pandas pyarrow` (pour `setup_datasets.py`)

```bash
docker --version && docker compose version
pip install boto3 pandas pyarrow
```

### Sans le script (démarre manuel)

```bash
cp .env.example .env
docker compose up -d minio postgres
docker compose run --rm minio-init          # crée le bucket + lifecycle
python setup_datasets.py                     # charge les datasets
docker compose up -d airflow-webserver airflow-scheduler
```

Premier lancement : ~2 min (téléchargement des images + création du bucket).

### Rechargement des datasets uniquement

```bash
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
| MinIO — console web | <http://localhost:9001> | `minioadmin` / `minioadmin123` |
| MinIO — API S3 | <http://localhost:9000> | — |
| Airflow | <http://localhost:8080> | `admin` / `admin` |

### Configuration (`.env`)

| Variable | Défaut | Description |
| --- | --- | --- |
| `MINIO_ROOT_USER` | `minioadmin` | Login MinIO et AWS CLI |
| `MINIO_ROOT_PASSWORD` | `minioadmin123` | Mot de passe MinIO et AWS CLI |

Le bucket unique est `data-lake`.

> Modifiez `.env` avant le **premier** `docker compose up` — le bucket n'est créé qu'une fois.
> Pour recréer : `docker compose down -v && docker compose up -d`

---

## Le pipeline `orders_pipeline`

Un DAG fonctionnel est fourni : `airflow/dags/orders_pipeline_dag.py` — pipeline **Bronze → Silver → Gold** qui lit les JSON `raw/orders/` dans MinIO, nettoie/agrège, écrit `gold/` de façon idempotente.

### Architecture du code

Le code métier est **séparé du DAG** dans `airflow/src/` (testable hors Airflow) :

```text
airflow/
├── dags/
│   └── orders_pipeline_dag.py      ← orchestration : appelle src/
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

### AWS CLI — alias `s3minio`

Le service `awscli` n'est pas démarré en permanence — il tourne à la demande.

> **Chemins de fichiers :** le dossier `data/` est monté en `/data` dans le conteneur.
> Utilisez des chemins Linux (`/data/example.csv`), pas Windows (`.\data\example.csv`).
> Raccourci : comme `working_dir` est `/data`, vous pouvez écrire `example.csv` sans préfixe.

**Bash / Zsh** — dans `~/.bashrc` ou `~/.zshrc`, puis `source ~/.bashrc` :

```bash
alias s3minio='docker compose --progress quiet run --rm awscli s3'
alias s3api='docker compose --progress quiet run --rm awscli s3api'
```

**PowerShell** — dans votre profil (`notepad $PROFILE`), puis `. $PROFILE` :

```powershell
function s3minio { docker compose --progress quiet run --rm awscli s3 $args }
function s3api   { docker compose --progress quiet run --rm awscli s3api $args }
```

Commandes fréquentes :

```bash
s3minio ls                                          # lister les buckets
s3minio ls s3://data-lake/ --recursive              # contenu du bucket
s3minio cp /data/example.csv s3://data-lake/raw/    # uploader un fichier
s3minio cp /data/ s3://data-lake/raw/sales/ --recursive   # uploader un dossier

s3api head-object --bucket data-lake --key raw/example.csv   # métadonnées
s3api put-bucket-encryption --bucket data-lake \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

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

## Structure du dépôt

```text
big-data-lab-infra/
├── docker-compose.yml      ← définition des services (MinIO + Airflow + AWS CLI)
├── .env.example            ← template de configuration
├── .env                    ← votre config locale (gitignored)
├── start.sh                ← point d'entrée : démarre tout + charge datasets
├── setup_datasets.py       ← chargement des datasets dans MinIO
├── requirements.txt        ← dépendances Python (lint / tests / local hors Docker)
├── airflow/
│   ├── dags/               ← DAGs (orchestration uniquement)
│   │   └── orders_pipeline_dag.py      ← Bronze→Silver→Gold (appelle src/)
│   └── src/               ← code métier testable hors Airflow
│       ├── config.py                  ← endpoints MinIO + chemins
│       ├── extract.py                 ← Bronze : JSON MinIO → Parquet
│       ├── transform.py               ← Silver : nettoyage + enrichissement
│       └── load.py                    ← Gold : agrégation → MinIO
└── data/                   ← fichiers à uploader via awscli (monté en /data)
```

> Staging Parquet et logs Airflow vivent dans des **volumes Docker nommés**
> (`airflow_data`, `airflow_logs`) — pas dans `data/`. C'est normal de ne pas
> les voir sur le disque hôte : ce sont des détails internes entre tâches.
>
> L'ancien modèle multi-utilisateur (déploiement centralisé sur Hidora, N buckets
> par binôme, users SSH/MinIO/Airflow) est conservé dans la branche
> `archive/multi-user-hidora`.

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

### `setup_datasets.py` échoue avec « Bucket introuvable »

Le service `minio-init` n'a pas encore tourné. Relancer dans l'ordre :

```bash
docker compose run --rm minio-init
python setup_datasets.py --endpoint http://localhost:9000
```

### Credentials AWS CLI incorrects

Vérifiez que `.env` existe et contient les bonnes valeurs, puis relancez depuis la racine du dépôt.
