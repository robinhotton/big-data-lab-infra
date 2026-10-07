# Lab Infra — Formation Big Data dans le Cloud

Environnement lab de la formation : **MinIO** (stockage objet S3) + **Airflow** (orchestration), avec chargement automatique des datasets.

Chaque apprenant lance **sa propre stack en local** — un seul bucket `data-lake`, un seul compte admin. Pas de déploiement centralisé.

> **Stockage : image `pgsty/minio`.** Le dépôt upstream `minio/minio` a été archivé
> en février 2026 et n'est plus téléchargeable — la stack bascule donc sur
> [`pgsty/minio`](https://hub.docker.com/r/pgsty/minio), un fork communautaire
> AGPLv3 du serveur MinIO, drop-in compatible (binaire `minio`, variables
> `MINIO_*`, format de données conservés, console admin restaurée). Pourquoi ce
> choix et ce qu'il implique : voir [§ Stockage](#stockage--pourquoi-pgstyminio).

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
   volumes nommés Airflow : airflow_data (données Airflow)
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

## Stockage : pourquoi `pgsty/minio`

### Le problème

En février 2026, le dépôt `minio/minio` (60k ⭐) a été passé en **fin de vie**
puis **archivé** : plus de maintenance, et surtout **plus de distribution binaire
ni d'images Docker**. Toute stack qui référence `minio/minio:...` ne démarre plus :

```bash
$ docker pull minio/minio:RELEASE.2024-10-13T13-34-11Z
denied: requested access to the resource is denied
```

C'était le cas de ce lab. Rien dans notre code n'était cassé — c'est la chaîne
d'approvisionnement qui a disparu.

### La solution retenue

[`pgsty/minio`](https://hub.docker.com/r/pgsty/minio) est un **fork AGPLv3**
maintenu par la communauté (Pigsty), qui republie le serveur MinIO avec la
console admin restaurée et les CVE corrigées. Pour ce lab, c'est un remplacement
**drop-in** :

| | Changé ? |
| --- | --- |
| Binaire `minio`, commande `server /data --console-address` | Non |
| Variables `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_KMS_SECRET_KEY` | Non |
| Client `mc` (`mb`, `encrypt`, `ilm`, …) | Non |
| Données existantes (layout `.minio.sys`), routes `/minio/*` | Non |
| Nom de l'image | Oui : `minio/minio` → `pgsty/minio` |

Concrètement, dans `docker-compose.yml` :

```yaml
minio:      image: pgsty/minio:RELEASE.2026-08-04T00-00-00Z   # avant : minio/minio:RELEASE.2024-…
minio-init: image: pgsty/mc:RELEASE.2026-08-04T00-00-00Z      # avant : minio/mc:RELEASE.2024-…
```

Aucune migration de données n'est nécessaire : une stack existante repart avec
ses volumes.

### Points d'attention

- **Licence AGPLv3.** MinIO est passé d'Apache 2.0 à AGPLv3 en 2021, et le fork
  conserve cette licence. Usage en formation locale : rien à faire. Si la stack
  était redistribuée ou intégrée à un service accessible en réseau, relire les
  termes AGPL.
- **Marque.** `MinIO®` est une marque déposée de MinIO, Inc. `pgsty/minio` est un
  fork communautaire indépendant, sans affiliation avec MinIO, Inc.
- **Fork gelé.** Depuis le 2026-08-06, la ligne de développement a été renommée
  [`pgsty/silo`](https://silo.pgsty.com/). Le tag `RELEASE.2026-08-04T00-00-00Z`
  utilisé ici reste publié et téléchargeable en l'état, mais ne recevra plus de
  correctifs. C'est une dette assumée pour la V1 (réparer vite pour les
  apprenants) : la migration est planifiée dans le dépôt de maintenance.

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

> ### ⚠️ Deux logins distincts — ne pas les échanger
>
> | Page | Login | Mot de passe |
> | --- | --- | --- |
> | **Airflow** <http://localhost:8080/login/> | `admin` | `admin` |
> | **MinIO** <http://localhost:9001/login> | `minioadmin` | `minioadmin123` |
>
> Chaque page refuse l'identifiant de l'autre : `minioadmin` sur Airflow, ou `admin`
> sur MinIO, affiche « Invalid login ». Ce n'est pas un bug — ce sont deux services
> et deux comptes. Et `:9000` est l'API S3, pas une page de login : elle ne montre
> rien dans un navigateur.

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
    ├── extract.py                 ← Bronze : lit les JSON orders (paginé)
    ├── transform.py                ← Silver : typage, dédup, total_price
    └── load.py                     ← Gold : agrégation CA → MinIO (idempotent)
```

Le DAG n'est qu'une **fine couche d'orchestration** : il appelle les modules métier
(`from extract import ...`, `from load import ...`) sans dupliquer de logique. Les
tâches communiquent via **XCom** (200 events/jour — volume léger, pas de staging
fichier). Un DAG qui passerait ses données par variable globale ne fonctionnerait pas
en LocalExecutor : chaque tâche tourne dans un processus séparé.

> **Pourquoi `src/` ?** Le code métier est testable indépendamment d'Airflow :
> `python airflow/src/extract.py` fonctionne hors conteneur (il ne manque que
> l'endpoint MinIO — passer `MINIO_ENDPOINT=http://localhost:9000`). C'est la bonne
> pratique (séparation orchestration / métier), utile à montrer en TP3. Les imports
> sont « à plat » (`from config import ...`), comme dans `CODE/` du cours.

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
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123"
BUCKET = "data-lake"
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

## Structure du dépôt (version apprenant)

```text
big-data-lab-infra/
├── docker-compose.yml       ← services (MinIO + Postgres + Airflow)
├── .env.example             ← template de configuration (10 variables)
├── .env                     ← votre config locale (gitignored)
├── .gitignore               ← empêche de committer .env
├── setup_datasets.py        ← seed des datasets (RNG seedé)
├── requirements.txt         ← dépendances Python
├── README.md                ← ce document
├── scripts/
│   ├── minio-init.sh        ← bucket data-lake + SSE-S3 + lifecycle
│   ├── datasets-init.sh     ← pip install + setup_datasets.py
│   └── airflow-init.sh      ← db migrate + user admin
└── airflow/
    ├── dags/                ← orchestration uniquement
    │   ├── orders_pipeline_dag.py    ← Bronze→Silver→Gold (boto3 direct)
    │   └── minio_conn_id_example.py  ← exemple S3Hook + conn_id
    └── src/                 ← code métier testable hors Airflow
        ├── config.py        ← endpoints MinIO + chemins (dataclass)
        ├── extract.py       ← Bronze : lit les JSON orders (paginé)
        ├── transform.py     ← Silver : typage, dédup, total_price
        └── load.py          ← Gold : agrégation CA → MinIO (idempotent)
```

> Les volumes Airflow (`airflow_data`, `airflow_logs`) sont des **volumes Docker
> nommés** — pas sur le disque hôte. C'est normal de ne pas les voir.

---

## Aller plus loin — mainteneur

La vérification d'intégrité de la stack (tests, lint, smoke test, CI,
observabilité, audit) est documentée dans
[`docs/README.md`](https://github.com/robinhotton/big-data-lab-infra/blob/main/docs/README.md)
du dépôt git. Elle n'est pas distribuée dans le zip apprenant.

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
