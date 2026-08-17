# Checklist J-1 — Préparation Formation Big Data dans le Cloud

À compléter la veille de chaque session. Durée estimée : 30 min.

Chaque apprenant lance sa propre stack en local — pas de déploiement centralisé.

---

## Poste formateur (J-1)

- [ ] `bash start.sh` exécuté avec succès sur le poste formateur
- [ ] `docker compose ps` → tous les services `healthy`
- [ ] MinIO console accessible : <http://localhost:9001> (minioadmin / minioadmin123)
- [ ] Airflow UI accessible : <http://localhost:8080> (admin / admin)
- [ ] DAG `orders_pipeline` visible dans Airflow, statut "unpaused"
- [ ] Vérifier les données dans le bucket `data-lake` :
  - [ ] `raw/sales/year=2026/month=03/` → 8 fichiers CSV
  - [ ] `raw/weather/weather_2025.csv`
  - [ ] `raw/taxi/yellow_tripdata_sample.parquet`
  - [ ] `raw/taxi/yellow_tripdata_2023-01.parquet` (si non sauté)
  - [ ] `raw/orders/2026/03/` → 31 fichiers JSON

## Credentials à partager (identiques pour tous)

| Variable | Valeur |
| --- | --- |
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `MINIO_ACCESS_KEY` | `minioadmin` |
| `MINIO_SECRET_KEY` | `minioadmin123` |
| `BUCKET` | `data-lake` |
| Airflow UI | <http://localhost:8080> — `admin` / `admin` |

## Supports distribués aux apprenants

- [ ] Lien vers le dépôt `big-data-lab-infra` partagé (clonage par les apprenants)
- [ ] Lien notebook Colab J2 préparé (ou confirmer que les apprenants créent le leur)
- [ ] Rappel : Colab ne peut pas joindre `localhost` → Jupyter local pour la connexion MinIO

## Documents formateur à avoir sous la main

> Les corrections et trames vivent dans le dépôt pédagogique [`cours-big-data-cloud`](https://github.com/robinhotton/cours-big-data-cloud), pas ici.

- [ ] Corrections QCM J1/J2/J3 : `QCM/corrections/` (dépôt cours)
- [ ] Corrections TP1/TP2/TP3 : `TP/corrections/` (dépôt cours)
- [ ] Trame live coding : `annexes/trame-live-coding.md` (dépôt cours)
- [ ] Guide formateur (infra) : `docs/guide-formateur.md` (présent dépôt)

## Groupes apprenants

- [ ] Composition des binômes / trios décidée et notée
- [ ] Vérifier que chaque poste a Docker Desktop démarré + Python + dépendances

---

## Checklist rapide J0 matin (30 min avant le démarrage)

Demander à chaque apprenant de lancer sa stack :

```bash
git clone https://github.com/robinhotton/big-data-lab-infra
cd big-data-lab-infra
bash start.sh
```

Vérifier en collectif :

```bash
# Services up ?
docker compose ps

# MinIO répond ?
curl -s http://localhost:9000/minio/health/live && echo "OK"

# Airflow répond ?
curl -s http://localhost:8080/health | python3 -m json.tool | grep status
```

- [ ] Chaque apprenant a MinIO console sur <http://localhost:9001>
- [ ] Chaque apprenant a Airflow UI sur <http://localhost:8080>
- [ ] Projeter la console MinIO pour le test d'accès collectif au démarrage J1
