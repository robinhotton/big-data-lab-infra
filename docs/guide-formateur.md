# Guide Formateur — Préparation de la Formation

Chaque apprenant lance **sa propre stack en local** (MinIO + Airflow + datasets) depuis ce dépôt.
Le formateur n'a pas de déploiement centralisé à gérer — il s'assure que chaque poste est prêt.

> L'ancien modèle multi-utilisateur (déploiement centralisé sur Hidora, N buckets par binôme)
> est conservé dans la branche `archive/multi-user-hidora`.

---

## Sommaire

- [Prérequis par poste](#prérequis-par-poste)
- [J-1 : Vérifier le dépôt](#j-1--vérifier-le-dépôt)
- [J0 matin : Vérifications avant session](#j0-matin--vérifications-avant-session)
- [En cours de formation](#en-cours-de-formation)
- [Fin de formation : nettoyage](#fin-de-formation--nettoyage)
- [Dépannage](#dépannage)

---

## Prérequis par poste

Chaque poste d'apprenant doit avoir :

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24 démarré
- Docker Compose ≥ 2.20
- Python 3 avec `boto3 pandas pyarrow`
- Git (pour cloner le dépôt)
- Accès Internet (téléchargement des images Docker + dataset NYC Taxi ~45 Mo)

```bash
docker --version && docker compose version
pip install boto3 pandas pyarrow
```

---

## J-1 : Vérifier le dépôt

Le formateur teste le lancement sur son propre poste pour valider que tout fonctionne :

```bash
git clone https://github.com/robinhotton/big-data-lab-infra
cd big-data-lab-infra
bash start.sh
```

Vérifier :

| Étape | Vérification |
| --- | --- |
| MinIO démarré | <http://localhost:9001> accessible (`minioadmin` / `minioadmin123`) |
| Airflow démarré | <http://localhost:8080> accessible (`admin` / `admin`) |
| Bucket créé | `data-lake` visible dans la console MinIO |
| Datasets chargés | `raw/sales/`, `raw/weather/`, `raw/taxi/`, `raw/orders/` dans `data-lake` |
| DAG visible | `orders_pipeline` dans Airflow → onglet **DAGs** |

```bash
# Vérifications en CLI
docker compose ps
curl -s http://localhost:9000/minio/health/live && echo "OK"
curl -s http://localhost:8080/health | python3 -m json.tool | grep status
```

> Si la connexion est limitée, `bash start.sh --skip-taxi-full` saute le téléchargement
> du dataset NYC Taxi. Les étudiants utiliseront le sample synthétique.

---

## J0 matin : Vérifications avant session

Demander à chaque apprenant de lancer sa stack 30 min avant le démarrage :

```bash
git clone https://github.com/robinhotton/big-data-lab-infra
cd big-data-lab-infra
bash start.sh
```

Vérifier en collectif que chacun a :

- [ ] MinIO console accessible sur <http://localhost:9001>
- [ ] Airflow UI accessible sur <http://localhost:8080>
- [ ] Le bucket `data-lake` contient les datasets (`raw/sales/`, `raw/taxi/`, etc.)

Credentials à partager (identiques pour tous, pas de secrets individuels) :

| Variable | Valeur |
| --- | --- |
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `MINIO_ACCESS_KEY` | `minioadmin` |
| `MINIO_SECRET_KEY` | `minioadmin123` |
| `BUCKET` | `data-lake` |
| Airflow UI | <http://localhost:8080> — `admin` / `admin` |

> Colab ne peut pas joindre un `localhost`. Pour les notebooks qui se connectent à MinIO,
> les étudiants doivent utiliser Jupyter en local (voir `README.md` § Colab → MinIO).

---

## En cours de formation

### Recharger les datasets (si un apprenant a cassé son bucket)

```bash
python setup_datasets.py --endpoint http://localhost:9000 --skip-taxi-full
```

Idempotent : les fichiers existants sont écrasés, le bucket est conservé.

---

## Fin de formation : nettoyage

Sur chaque poste d'apprenant :

```bash
# Arrêter les services (données conservées)
docker compose down

# Arrêter ET supprimer toutes les données (reset complet)
docker compose down -v
```

---

## Dépannage

### MinIO inaccessible

```bash
docker compose logs minio | tail -20
# Si "permission denied" sur /data → vérifier les droits du volume Docker
docker compose down -v && bash start.sh
```

### Airflow ne démarre pas

```bash
docker compose logs airflow-webserver | tail -20
# Cause fréquente : airflow-init pas encore terminé
# Attendre 30s puis relancer :
docker compose up -d airflow-webserver airflow-scheduler
```

### DAG orders_pipeline non visible dans Airflow

```bash
# Le DAG est dans airflow/dags/ — vérifier qu'il est bien monté
docker compose exec airflow-scheduler airflow dags list | grep orders
# Si absent : attendre 60s (refresh automatique du scheduler)
```

### setup_datasets.py échoue avec "Bucket introuvable"

Le service `minio-init` n'a pas encore tourné. Relancer dans l'ordre :

```bash
docker compose run --rm minio-init
python setup_datasets.py --endpoint http://localhost:9000
```
