# Guide Formateur — Préparation de la Formation

Ce document décrit tout ce que le formateur doit faire **avant que les apprenants arrivent**.
Aucune action n'est requise des apprenants sur l'infrastructure.

---

## Sommaire

- [Prérequis](#prérequis)
- [J-1 : Déploiement de la stack](#j-1--déploiement-de-la-stack)
- [J0 matin : Vérifications avant session](#j0-matin--vérifications-avant-session)
- [Distribuer les credentials aux apprenants](#distribuer-les-credentials-aux-apprenants)
- [En cours de formation](#en-cours-de-formation)
- [Fin de formation : nettoyage](#fin-de-formation--nettoyage)
- [Dépannage](#dépannage)

---

## Prérequis

### Sur le serveur Hidora (ou machine locale)

- Docker ≥ 24 et Docker Compose ≥ 2.20
- Python 3.11 avec `boto3 pandas pyarrow`
- Ports ouverts : `9000` (MinIO API), `9001` (MinIO console), `8080` (Airflow)

> **AlmaLinux 8 (Hidora)** — Python 3.6 est installé par défaut mais trop vieux pour boto3.
> Installer Python 3.11 avant tout :
>
> ```bash
> dnf install python3.11 python3.11-pip -y --nogpgcheck
> python3.11 -m pip install boto3 pandas pyarrow -q
> ```

> **Pas de Git sur Hidora** — déployer via SCP depuis le poste formateur :
>
> ```bash
> # Depuis le poste formateur (PowerShell / WSL)
> scp -P 11717 -r /chemin/vers/big-data-lab-infra \
>   root@node199038-iso-big-data-cloud.sh1.hidora.com:/root/
> ```

---

## J-1 : Déploiement de la stack

### Étape 1 — Corriger les fins de ligne et configurer `.env`

```bash
# Les scripts sont édités sous Windows → corriger les CRLF avant tout
find . -type f -not -path './.git/*' | xargs sed -i 's/\r//'

cp .env.example .env
```

Modifier `.env` — adapter obligatoirement `HIDORA_HOST` et `NB_BINOMES` :

```bash
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
NB_BINOMES=11       # ← adapter au nombre de binômes réels
SSH_PASSWORD=Diginamic34_
HIDORA_HOST=node199038-iso-big-data-cloud.sh1.hidora.com  # ← URL de la VM
SSH_PORT=11717
MINIO_API_PORT=11700
MINIO_CONSOLE_PORT=11701
AIRFLOW_PORT=11702
```

> Si `HIDORA_HOST` reste à `localhost`, les `credentials.txt` distribués aux apprenants
> contiendront la mauvaise URL.

### Étape 2 — Lancer la stack complète

```bash
# Depuis la racine du dépôt
sudo bash formateur-start.sh --nb-binomes 11
```

Ce script fait tout automatiquement :

| Étape | Action | Vérification |
| --- | --- | --- |
| 1 | Démarrage MinIO + PostgreSQL | `docker compose ps` → `healthy` |
| 2 | Création buckets + lifecycle | N buckets `data-lake-binome-01..NN` |
| 3 | CSV transactions + météo (TP1) | `raw/sales/year=2026/month=03/` + `raw/weather/` dans chaque bucket |
| 4 | Taxi sample + full NYC TLC (TP2) | `raw/taxi/yellow_tripdata_sample.parquet` + `yellow_tripdata_2023-01.parquet` |
| 5 | Orders JSON (TP3, 31 fichiers) | `raw/orders/2026/03/orders_*.json` dans chaque bucket |
| 6 | Démarrage Airflow | UI accessible sur `:8080` |

Durée estimée : **10 à 15 minutes** selon la connexion réseau (téléchargement NYC Taxi full ~45 Mo inclus).

> Si la connexion est limitée, ajoutez `--skip-taxi-full` pour sauter le téléchargement
> du dataset réel NYC Taxi. Les étudiants utiliseront alors uniquement le sample synthétique.

### Étape 3 — Vérifier le déploiement

```bash
# Services actifs
docker compose -f docker-compose.yml ps

# MinIO health
curl -s http://localhost:9000/minio/health/live && echo "OK"

# Airflow health
curl -s http://localhost:8080/health | python3.11 -m json.tool | grep status

# DAG visible et actif
docker compose -f docker-compose.yml exec -T airflow-scheduler \
  airflow dags list | grep orders
# Si is_paused=True → dépausé :
docker compose -f docker-compose.yml exec -T airflow-scheduler \
  airflow dags unpause orders_pipeline
```

> **Note :** le CLI `aws` livré avec AlmaLinux 8 (Python 3.6) est cassé.
> Utiliser `python3.11` avec `boto3` pour toute vérification programmatique.

---

## J0 matin : Vérifications avant session

Vérifier 30 minutes avant le démarrage :

```bash
# Services encore up ?
docker compose -f docker-compose.yml ps

# MinIO répond ?
curl -s http://localhost:9000/minio/health/live && echo "OK"

# Airflow répond ?
curl -s http://localhost:8080/health | python3.11 -m json.tool | grep status
```

Si un service est tombé :

```bash
# Redémarrer sans perdre les données
docker compose -f docker-compose.yml up -d

# Si les données ont disparu (volume supprimé), recharger
python3.11 setup_datasets.py \
  --endpoint http://localhost:9000 \
  --nb-binomes 11
```

---

## Distribuer les credentials aux apprenants

Chaque binôme reçoit ces informations (à copier dans le notebook Colab) :

| Variable | Valeur |
| --- | --- |
| `MINIO_ENDPOINT` | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11700` |
| `MINIO_ACCESS_KEY` | `binomeXX` |
| `MINIO_SECRET_KEY` | `Diginamic34_` |
| `BUCKET` | `data-lake-binome-XX` (XX = numéro du binôme) |

Airflow UI : `http://node199038-iso-big-data-cloud.sh1.hidora.com:11702` — `binomeXX` / `Diginamic34_` (rôle Viewer)

> Pour des credentials individuels par binôme (isolation stricte), voir
> `docs/create_ssh_users.md` §Credentials MinIO.

---

## En cours de formation

### Rechargement partiel (si un binôme a tout cassé)

```bash
# Recharger uniquement les datasets d'un bucket (ex: binome03)
python3.11 setup_datasets.py \
  --endpoint http://localhost:9000 \
  --prefix-bucket data-lake-binome-03 \
  --nb-binomes 1 \
  --skip-taxi-full
```

### Ajout d'un nouveau binôme en cours de session

```bash
# Charger les datasets sur un nouveau bucket
python3.11 setup_datasets.py \
  --endpoint http://localhost:9000 \
  --prefix-bucket data-lake-binome-12 \
  --nb-binomes 1 \
  --skip-taxi-full
```

---

## Fin de formation : nettoyage

```bash
# Arrêter les services (données conservées)
docker compose -f docker-compose.yml down

# Arrêter ET supprimer toutes les données (reset complet)
docker compose -f docker-compose.yml down -v
```

---

## Dépannage

### MinIO inaccessible

```bash
docker compose -f docker-compose.yml logs minio | tail -20
# Si "permission denied" sur /data → vérifier les droits du volume
docker compose -f docker-compose.yml down -v && sudo bash formateur-start.sh
```

### Airflow ne démarre pas

```bash
docker compose -f docker-compose.yml logs airflow-webserver | tail -20
# Cause fréquente : airflow-init pas encore terminé
# Attendre 30s puis relancer :
docker compose -f docker-compose.yml up -d airflow-webserver airflow-scheduler
```

### DAG orders_pipeline non visible dans Airflow

```bash
# Le DAG est dans airflow/dags/ — vérifier qu'il est bien monté
docker compose -f docker-compose.yml exec airflow-scheduler \
  airflow dags list | grep orders
# Si absent : attendre 60s (refresh automatique du scheduler)
```

### setup_datasets.py échoue avec "Bucket introuvable"

Le script `minio-init` n'a pas encore tourné. Relancer dans l'ordre :

```bash
docker compose -f docker-compose.yml run --rm minio-init
python3.11 setup_datasets.py --endpoint http://localhost:9000 --nb-binomes 11
```
