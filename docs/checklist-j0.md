# Checklist J-1 — Préparation Formation Big Data dans le Cloud

À compléter la veille de chaque session. Durée estimée : 30-45 min.

---

## Infrastructure Hidora

- [ ] `bash formateur-start.sh --endpoint http://[hidora-url]:9000 --nb-binomes N` exécuté avec succès
- [ ] `docker compose -f docker-compose.yml ps` → tous les services `healthy`
- [ ] MinIO console accessible : `http://[hidora-url]:9001` (minioadmin / minioadmin123)
- [ ] Airflow UI accessible : `http://[hidora-url]:8080` (admin / admin)
- [ ] DAG `orders_pipeline` visible dans Airflow, statut "unpaused"
- [ ] Vérifier les données dans au moins un bucket :
  - [ ] `raw/sales/year=2026/month=03/` → 8 fichiers CSV
  - [ ] `raw/weather/weather_2025.csv`
  - [ ] `raw/taxi/yellow_tripdata_sample.parquet`
  - [ ] `raw/taxi/yellow_tripdata_2023-01.parquet` (si non sauté)
  - [ ] `raw/orders/2026/03/` → 31 fichiers JSON

## Credentials apprenants

- [ ] Tableau de distribution préparé :

| Binôme | MINIO_ENDPOINT | MINIO_ACCESS_KEY | MINIO_SECRET_KEY | BUCKET |
| --- | --- | --- | --- | --- |
| 01 | `http://[hidora-url]:9000` | `minioadmin` | `minioadmin123` | `data-lake-binome-01` |
| 02 | … | … | … | `data-lake-binome-02` |
| … | | | | |

- [ ] Airflow UI : `http://[hidora-url]:8080` — admin / admin (partagé ou lecture seule)

## Supports distribués aux apprenants

- [ ] CSV TP1 déposés sur Teams (`Supports de cours / Datasets / TP1`)
- [ ] Lien notebook Colab J2 préparé (ou confirmer que les apprenants créent le leur)
- [ ] URL Hidora confirmée et testée depuis un réseau externe (≠ réseau formateur)

## Documents formateur à avoir sous la main

> Ces documents vivent dans le dépôt pédagogique [`cours-big-data-cloud`](https://github.com/robinhotton/cours-big-data-cloud), pas ici.

- [ ] Corrections QCM J1 : `QCM/corrections/corrections-j1.md`
- [ ] Corrections QCM J2 : `QCM/corrections/corrections-j2.md`
- [ ] Corrections QCM J3 : `QCM/corrections/corrections-j3.md`
- [ ] Corrections TP1 : `TP/corrections/01-tp-data-lake-corrections.md`
- [ ] Corrections TP2 : `TP/corrections/02-tp-processing-ia-corrections.md`
- [ ] Corrections TP3 : `TP/corrections/03-tp-fil-rouge-corrections.md`
- [ ] Trame live coding : `annexes/trame-live-coding.md`
- [ ] Guide formateur (infra) : `docs/guide-formateur.md` dans le présent dépôt

## Plan B réseau (si Hidora inaccessible)

- [ ] Docker installé sur le poste formateur
- [ ] `docker compose -f docker-compose.yml up -d` testé en local
- [ ] MinIO local accessible sur `http://localhost:9001`
- [ ] Airflow local accessible sur `http://localhost:8080`

## Groupes apprenants (11 personnes)

- [ ] Composition des binômes / trios décidée et notée
- [ ] Numéros de buckets assignés à chaque groupe

---

## Checklist rapide J0 matin (30 min avant le démarrage)

```bash
# Services encore up ?
docker compose -f docker-compose.yml ps

# MinIO répond ?
curl -s http://[hidora-url]:9000/minio/health/live && echo "OK"

# Airflow répond ?
curl -s http://[hidora-url]:8080/health | python3 -m json.tool | grep status
```

- [ ] Test connexion depuis le réseau de la salle (pas depuis le VPN formateur)
- [ ] Projeter la console MinIO pour le test d'accès collectif au démarrage J1
