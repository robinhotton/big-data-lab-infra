# Plan B — Déploiement Local

> À utiliser si la connexion à Hidora est impossible (réseau limité, problème serveur).
> La stack tourne entièrement sur votre machine : MinIO + Airflow via Docker, AWS CLI en local.

---

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24 installé et démarré
- Terminal : PowerShell (Windows), Terminal (macOS/Linux)

---

## 1. Démarrer la stack locale

Depuis la racine du dépôt :

```bash
cp .env.example .env
docker compose up -d
```

Vérifier que tout tourne :

```bash
docker compose ps
```

Les services `minio` et `airflow-webserver` doivent être en `running`.

---

## 2. Installer AWS CLI

### Windows

Télécharger et exécuter l'installeur MSI :
<https://awscli.amazonaws.com/AWSCLIV2.msi>

Vérifier dans un nouveau PowerShell :

```powershell
aws --version
```

### macOS

```bash
brew install awscli
```

### Linux (Debian/Ubuntu)

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install
```

---

## 3. Configurer AWS CLI pour MinIO local

```bash
aws configure set aws_access_key_id minioadmin
aws configure set aws_secret_access_key minioadmin123
aws configure set default.region us-east-1
```

Ajouter les aliases (à coller dans votre terminal en début de session) :

**Bash / Zsh** :

```bash
alias s3minio='aws s3 --endpoint-url http://localhost:9000'
alias s3api='aws s3api --endpoint-url http://localhost:9000'
```

**PowerShell** :

```powershell
function s3minio { aws s3 --endpoint-url http://localhost:9000 $args }
function s3api   { aws s3api --endpoint-url http://localhost:9000 $args }
```

> 💡 Pro Tip : ajoutez ces aliases dans votre profil shell (`~/.bashrc`, `~/.zshrc`, ou `$PROFILE` en PowerShell) pour ne pas les retaper à chaque session.

---

## 4. Créer votre bucket et charger les datasets

```bash
# Créer votre bucket (remplacez XX par votre numéro)
s3api create-bucket --bucket data-lake-binome-XX

# Vérifier
s3minio ls
```

Charger les datasets (depuis la racine du dépôt) :

```bash
pip install boto3 pandas pyarrow -q
python setup_datasets.py --endpoint http://localhost:9000 --nb-binomes 1
```

---

## 5. Vérifier l'accès

```bash
s3minio ls s3://data-lake-binome-01/
```

**Vous devriez voir** les datasets pré-chargés sous `raw/`.

| Interface | URL | Identifiants |
| --- | --- | --- |
| MinIO Console | <http://localhost:9001> | `minioadmin` / `minioadmin123` |
| Airflow UI | <http://localhost:8080> | `admin` / `admin` |

---

## 6. Adapter les commandes du TP

Dans tous les exercices, remplacez `[hidora-url]:9000` par `localhost:9000`.

Les alias `s3minio` et `s3api` fonctionnent exactement de la même façon — seul l'endpoint change.

Pour Colab → MinIO local, le notebook doit tourner sur la même machine (Colab ne peut pas accéder à votre `localhost`). Utilisez les notebooks directement en local avec Jupyter :

```bash
pip install jupyter pyspark -q
jupyter notebook
```
