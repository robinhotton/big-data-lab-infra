# Lab Infra — Formation Big Data dans le Cloud

Environnement lab de la formation : **MinIO** + **Airflow** + AWS CLI, et chargement automatique des datasets.

Chaque apprenant lance **sa propre stack en local** — un seul bucket `data-lake`, un seul compte admin. Pas de déploiement centralisé.

> Ce dépôt est le volet **infrastructure** de la formation. Les supports de cours, TP et annexes pédagogiques vivent dans le dépôt séparé [`cours-big-data-cloud`](https://github.com/robinhotton/cours-big-data-cloud).

---

## Démarrage (une commande)

```bash
# Depuis la racine du dépôt — démarre tout et charge les datasets
bash start.sh

# Sans le dataset NYC Taxi (~45 Mo, utile si connexion limitée)
bash start.sh --skip-taxi-full
```

Ce script enchaîne automatiquement :

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
> **Internet requis** pour le téléchargement du taxi full (~45 Mo depuis NYC TLC).
> Ajoutez `--skip-taxi-full` si la connexion est limitée.

### Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24
- Docker Compose ≥ 2.20
- Python 3 avec `boto3 pandas pyarrow` (pour `setup_datasets.py`)

```bash
docker --version && docker compose version
pip install boto3 pandas pyarrow
```

### Rechargement des datasets uniquement

Si la stack tourne déjà et que vous voulez juste recharger les données :

```bash
python setup_datasets.py --endpoint http://localhost:9000

# Options de rechargement partiel :
python setup_datasets.py --skip-taxi-full          # sans re-télécharger les 45 Mo
python setup_datasets.py --skip-csv --skip-taxi    # orders TP3 uniquement
python setup_datasets.py --csv-rows 100000         # CSV réduits (développement)
```

---

## Démarrage manuel (sans le script)

```bash
# 1. Copier la config (une seule fois)
cp .env.example .env

# 2. Lancer tous les services + créer le bucket
docker compose up -d
docker compose run --rm minio-init

# 3. Charger les datasets
python setup_datasets.py

# 4. Vérifier
docker compose ps
```

Premier lancement : ~2 min (téléchargement des images + création du bucket).

---

## Services & Accès

| Service | URL | Identifiants par défaut |
| --- | --- | --- |
| MinIO — console web | <http://localhost:9001> | `minioadmin` / `minioadmin123` |
| MinIO — API S3 | <http://localhost:9000> | — |
| Airflow | <http://localhost:8080> | `admin` / `admin` |

---

## Configuration (`.env`)

| Variable | Défaut | Description |
| --- | --- | --- |
| `MINIO_ROOT_USER` | `minioadmin` | Login MinIO et AWS CLI |
| `MINIO_ROOT_PASSWORD` | `minioadmin123` | Mot de passe MinIO et AWS CLI |

Le bucket unique est `data-lake`.

> Modifiez `.env` avant le **premier** `docker compose up` — le bucket n'est créé qu'une fois.
> Pour recréer : `docker compose down -v && docker compose up -d`

---

## AWS CLI

Le service `awscli` n'est pas démarré en permanence — il tourne uniquement à la demande.

> **Chemins de fichiers :** le dossier `data/` est monté en `/data` dans le conteneur.
> Utilisez toujours des chemins Linux (`/data/example.csv`), jamais des chemins Windows (`.\data\example.csv`).
> Raccourci : comme `working_dir` est `/data`, vous pouvez écrire juste `example.csv` sans préfixe.

### Alias (recommandé)

**Bash / Zsh** — ajoutez dans `~/.bashrc` ou `~/.zshrc`, puis `source ~/.bashrc` :

```bash
alias s3minio='docker compose --progress quiet run --rm awscli s3'
alias s3api='docker compose --progress quiet run --rm awscli s3api'
```

**PowerShell** — ajoutez dans votre profil (`notepad $PROFILE`), puis `. $PROFILE` :

```powershell
# Exécutez ces commandes depuis la racine du dépôt
function s3minio { docker compose --progress quiet run --rm awscli s3 $args }
function s3api   { docker compose --progress quiet run --rm awscli s3api $args }
```

### Commandes fréquentes

> **Note PowerShell :** pas de `\` pour continuer une ligne — utilisez `` ` `` ou écrivez la commande sur une seule ligne.

```bash
# Lister les buckets
s3minio ls

# Lister le contenu du bucket
s3minio ls s3://data-lake/ --recursive

# Uploader un fichier (depuis data/ → /data/ dans le conteneur)
s3minio cp /data/example.csv s3://data-lake/raw/

# Uploader un dossier entier
s3minio cp /data/ s3://data-lake/raw/sales/ --recursive

# Métadonnées d'un objet
s3api head-object --bucket data-lake --key raw/example.csv

# Activer le chiffrement SSE-AES256 (une seule ligne)
s3api put-bucket-encryption --bucket data-lake --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

# Créer des "dossiers" (objets vides)
s3api put-object --bucket data-lake --key cleansed/
s3api put-object --bucket data-lake --key curated/

```

---

## Airflow

Deux DAGs sont fournis :

- `airflow/dags/example_pipeline.py` — DAG d'intro **illustratif** (tâches en `print`, sans I/O). Pédagogique : montre la structure d'un DAG sans complexité.
- `airflow/dags/orders_pipeline.py` — pipeline **fonctionnel** Bronze → Silver → Gold : lit les JSON `raw/orders/` dans MinIO, nettoye/agrège, écrit `gold/` de façon idempotente.

### Le vrai pipeline (`orders_pipeline`) — architecture

Le code métier est **séparé du DAG** dans `airflow/src/` (testable hors Airflow) :

```
airflow/
├── dags/
│   ├── example_pipeline.py        ← DAG d'intro (print, illustratif)
│   └── orders_pipeline_dag.py      ← orchestration : appelle src/
└── src/                            ← code métier (pas d'Airflow dedans)
    ├── config.py                  ← endpoints MinIO + chemins (dataclass)
    ├── extract.py                 ← Bronze : JSON MinIO → Parquet staging
    ├── transform.py                ← Silver : typage, dédup, total_price
    └── load.py                     ← Gold : agrégation CA → MinIO (idempotent)
```

Le DAG n'est qu'une **fine couche d'orchestration** : `from src import extract, transform, load`. Les tâches communiquent via **staging Parquet** (`data/staging/`) plutôt que par XCom, adapté aux volumes pandas.

> **Pourquoi `src/` ?** Le code métier est testable indépendamment d'Airflow :
> `python -m airflow.src.extract` fonctionne hors conteneur. C'est la bonne pratique
> (séparation orchestration / métier), utile à montrer en TP3.

### Déclencher un DAG

Les DAGs démarrent **en pause** (`DAGS_ARE_PAUSED_AT_CREATION: "true"`). Dans l'UI :

1. <http://localhost:8080> → onglet **DAGs**
2. Activer le DAG (bouton on/off) puis le déclencher (**Trigger DAG w/ config**)
3. Pour `orders_pipeline`, la date logique (`ds`) détermine le fichier lu dans MinIO

> `airflow-init` et `minio-init` apparaissent en `exited` dans `docker compose ps` — c'est normal, ils ne s'exécutent qu'une seule fois au démarrage.
>
> `_PIP_ADDITIONAL_REQUIREMENTS` (boto3, pandas, pyarrow) s'installe au premier
> démarrage des conteneurs Airflow : prévoir ~30-60s supplémentaires la première fois.

---

## Colab → MinIO (local)

**Google Colab** : [colab.research.google.com](https://colab.research.google.com) — notebooks PySpark dans le navigateur, aucune installation requise.

> Colab ne peut pas accéder à votre `localhost`. Pour connecter Colab à un MinIO local,
> le notebook doit tourner sur la même machine — utilisez Jupyter en local à la place :
>
> ```bash
> pip install jupyter pyspark -q
> jupyter notebook
> ```

Les notebooks de TP contiennent le code de connexion complet. Les credentials à renseigner :

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

## Commandes de Gestion

```bash
# Arrêter (données conservées)
docker compose down

# Arrêter + supprimer toutes les données
docker compose down -v

# Logs en temps réel
docker compose logs -f
docker compose logs -f minio
docker compose logs -f airflow-scheduler

# Redémarrer un service
docker compose restart airflow-webserver
```

---

## Structure du Dossier

```text
big-data-lab-infra/
├── docker-compose.yml      ← définition des services (MinIO + Airflow + AWS CLI)
├── .env.example            ← template de configuration
├── .env                    ← votre config locale (gitignored)
├── .gitignore
├── start.sh                ← point d'entrée : démarre tout + charge datasets
├── setup_datasets.py       ← chargement des datasets dans MinIO
├── generate_orders_dataset.py
├── requirements.txt        ← dépendances Python (lint / tests / local hors Docker)
├── airflow/
│   ├── dags/               ← DAGs (orchestration uniquement)
│   │   ├── example_pipeline.py        ← intro illustratif (print)
│   │   └── orders_pipeline_dag.py      ← Bronze→Silver→Gold (appelle src/)
│   └── src/               ← code métier testable hors Airflow
│       ├── config.py                  ← endpoints MinIO + chemins
│       ├── extract.py                 ← Bronze : JSON MinIO → Parquet
│       ├── transform.py               ← Silver : nettoyage + enrichissement
│       └── load.py                    ← Gold : agrégation → MinIO
├── minio/
│   └── init-buckets.sh      ← création du bucket + lifecycle
└── data/                   ← staging Parquet + fichiers locaux
                               (monté en /opt/airflow/data et /data)
```

---

## Documentation

| Document | Description |
| --- | --- |
| [`docs/guide-formateur.md`](docs/guide-formateur.md) | Préparation de la formation, vérifications J0 |
| [`docs/checklist-j0.md`](docs/checklist-j0.md) | Checklist veille de session |
| [`docs/plan-b-local.md`](docs/plan-b-local.md) | Déploiement local détaillé |

> L'ancien modèle multi-utilisateur (déploiement centralisé sur Hidora, N buckets par binôme,
> users SSH/MinIO/Airflow) est conservé dans la branche `archive/multi-user-hidora`.

---

## Dépannage

**Port déjà utilisé :**

```bash
# Identifier le processus qui utilise le port 9000
lsof -i :9000        # macOS / Linux
netstat -ano | findstr :9000   # Windows
```

Modifiez le mapping de port dans `docker-compose.yml` (`"9002:9000"` par exemple).

**Airflow inaccessible au démarrage :**
Attendez que `airflow-init` soit terminé (`exited 0`) avant d'ouvrir <http://localhost:8080>. Vérifiez avec `docker compose logs airflow-init`.

**Credentials AWS CLI incorrects :**
Vérifiez que `.env` existe et contient les bonnes valeurs, puis relancez depuis la racine du dépôt.
