# Vérification d'intégrité de la stack

Documentation **mainteneur**. Elle ne part pas dans le zip apprenant
(`export-ignore` dans `.gitattributes`) : elle décrit comment vérifier que la
stack est saine — tests, lint, smoke test, CI, observabilité, rétention.

> La documentation **d'utilisation** (démarrer la stack, logins, pipeline,
> dépannage) est dans [`README.md`](../README.md), à la racine. C'est lui qui
> est distribué aux apprenants.

---

## Tests & lint

Le code métier (`airflow/src/`) est testé **hors Docker et hors Airflow**. La
suite couvre `config`, `extract`, `transform`, `load` et le contrat des DAGs
(moteur S3 mocké avec `moto`).

```bash
pip install -r requirements.txt   # installe aussi pytest + ruff + mypy + moto
pytest -q                         # lance la suite
pytest -q -k extract              # filtre par nom

ruff check .                      # lint
ruff check --fix .                # corrige les erreurs auto (imports, etc.)
ruff format .                     # formate le dépôt
ruff format --check .             # vérifie sans toucher (c'est ce que la CI exige)
mypy                              # types du code métier (airflow/src/)
```

Style de logging imposé par l'ADR-001 (`%s` lazy, pas de f-string) :
[`adr/001-logging-style.md`](adr/001-logging-style.md).

---

## Tests smoke (intégration réelle)

`scripts/smoke-test.sh` démarre la stack dans un **projet isolé** (`lab-smoke`,
ports dépubliés) et vérifie bout en bout que le lab est réellement utilisable :

1. MinIO, Postgres et Airflow passent `healthy` ;
2. `minio-init` crée le bucket `data-lake`, le chiffrement SSE-S3 et les règles
   de lifecycle, puis est **relancé pour prouver l'idempotence** ;
3. les jobs one-shot (`airflow-init`, `datasets-init`) sortent en exit 0.

```bash
./scripts/smoke-test.sh
```

> Le smoke test peut tourner **en parallèle d'un lab déjà démarré** : il n'occupe
> aucun port publié (voir `docker-compose.smoke.yml`).

---

## CI GitHub Actions

`.github/workflows/ci.yml` lance automatiquement :

| Job          | Déclencheur                | Contenu                                                             |
| ------------ | -------------------------- | ------------------------------------------------------------------- |
| lint & tests | push / PR                  | `ruff check` + `ruff format --check` + `mypy` + `pytest -q` (JUnit en artifact) |
| smoke        | push / PR                  | `scripts/smoke-test.sh` + `docker pull` des images épinglées         |
| smoke        | cron mensuel (le 3 à 6h17) | re-vérification supply-chain des images                             |

Les logs de la stack et les rapports sont téléchargeables en **artifacts GitHub**
(rétention 14 jours) même quand le job échoue.

`.github/workflows/release.yml` publie à chaque tag `v*` le zip apprenant
(`git archive` + les règles `export-ignore` de `.gitattributes`), puis **refuse
de publier** si un chemin mainteneur (`tests/`, `.github/`, `docs/`,
`pyproject.toml`, `smoke-test.sh`, `stack-status.sh`) fuit dans l'archive.

---

## Contrôle & observabilité

```bash
./scripts/stack-status.sh              # vue ops complète en une commande
./scripts/stack-status.sh --offline    # sans vérification réseau des images
STATUS_SECTIONS=svc,err ./scripts/stack-status.sh   # sections ciblées
```

Affiche : état des services **et ExitCode des jobs one-shot**, erreurs récentes
(bruit du premier `db migrate` filtré), usage disque des volumes du lab,
rotation des logs Docker, disponibilité des images épinglées.

---

## Logs & politiques de rétention

```bash
docker compose logs -f airflow-scheduler          # stdout des conteneurs
docker compose logs -f minio
```

- Logs Docker **rotés** (`json-file`, max 10 Mo × 3 fichiers) sur tous les
  services — la stack ne remplit pas le disque de l'hôte.
- Logs Airflow des tâches dans MinIO : `s3://data-lake/airflow-logs/` (via
  `AIRFLOW__LOGGING__REMOTE_*`), règle de lifecycle de **30 jours**.
- Données `raw/` : règle de lifecycle de **365 jours**.

```bash
docker compose exec minio-init mc ilm rule ls local/data-lake   # lifecycle active
docker compose exec minio-init mc admin info local              # santé MinIO
```

---

## Migration de nom de projet (une fois)

Depuis V2, le projet Compose est épinglé avec `name: lab` pour que les noms de
conteneurs soient stables (`lab-minio`, `lab-postgres`, …) — prérequis du smoke
test et de `stack-status.sh`. Si la stack a été montée **avant** cette version,
les conteneurs existants restent rattachés à l'ancien nom de projet
(`big-data-lab-infra`). Une seule fois :

```bash
docker compose -p big-data-lab-infra down && docker compose up -d
```

Les volumes (données MinIO, Postgres) sont conservés.

---

## Documents de maintenance

| Document                              | Contenu                                                    |
| ------------------------------------- | ---------------------------------------------------------- |
| [`AUDIT.md`](AUDIT.md)                | bonnes pratiques en place, anomalies par gravité           |
| [`HARDENING-ROADMAP.md`](HARDENING-ROADMAP.md) | plan V2 (CI, tests, durcissement) / V3 (silo)     |
| [`adr/001-logging-style.md`](adr/001-logging-style.md) | ADR : `%s` lazy plutôt qu'un f-string      |

---

## Structure du dépôt (complet)

Le zip apprenant ne contient que la partie **utilisation**. Le dépôt git ajoute
l'outillage de vérification :

```text
big-data-lab-infra/
├── README.md                     ← doc d'utilisation (dans le zip apprenant)
├── docker-compose.yml            ← services
├── docker-compose.smoke.yml      ← [mainteneur] overlay smoke : ports dépubliés
├── .env.example                  ← template de configuration (10 variables)
├── .gitignore                    ← dans le zip : protège .env de l'apprenant
├── .gitattributes                ← [mainteneur] règles export-ignore
├── setup_datasets.py             ← seed programmatique (RNG seedé)
├── requirements.txt              ← runtime + dev (pytest, ruff, mypy, moto)
├── airflow/
│   ├── dags/                     ← orchestration uniquement
│   └── src/                      ← code métier (imports à plat)
├── scripts/
│   ├── minio-init.sh             ← bucket + SSE-S3 + lifecycle
│   ├── datasets-init.sh          ← pip install + setup_datasets.py
│   ├── airflow-init.sh           ← db migrate + user admin
│   ├── smoke-test.sh             ← [mainteneur] smoke test isolé
│   └── stack-status.sh           ← [mainteneur] vue ops
├── docs/                         ← [mainteneur] tout ce dossier
│   ├── README.md                 ← ce fichier
│   ├── AUDIT.md
│   ├── HARDENING-ROADMAP.md
│   └── adr/001-logging-style.md
├── tests/                        ← [mainteneur] suite pytest
│   ├── README.md
│   ├── conftest.py
│   ├── test_dag_contract.py
│   └── airflow_src/
├── pyproject.toml                ← [mainteneur] config ruff + mypy + pytest
└── .github/workflows/            ← [mainteneur] ci.yml + release.yml
```

Les chemins marqués `[mainteneur]` figurent en `export-ignore` dans
`.gitattributes` : `git archive` — et donc le zip publié à chaque tag — les
exclut. Seul `.gitignore` fait exception et reste dans le zip : c'est lui qui
empêche un apprenant de committer son `.env` (credentials réels).
