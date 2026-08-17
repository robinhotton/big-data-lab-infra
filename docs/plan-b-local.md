# Déploiement Local — Guide détaillé

La stack tourne entièrement sur votre machine : MinIO + Airflow via Docker, AWS CLI en local.
C'est le mode de fonctionnement normal — chaque apprenant lance sa propre stack.

> Pour le démarrage en une commande, voir le `README.md` (`bash start.sh`).
> Ce document détaille les étapes manuelles et la configuration AWS CLI.

---

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) ≥ 24 installé et démarré
- Python 3 avec `boto3 pandas pyarrow`
- Terminal : PowerShell (Windows), Terminal (macOS/Linux)

---

## 1. Démarrer la stack locale

Depuis la racine du dépôt :

```bash
cp .env.example .env
docker compose up -d
docker compose run --rm minio-init   # crée le bucket data-lake + lifecycle
```

Vérifier que tout tourne :

```bash
docker compose ps
```

Les services `minio` et `airflow-webserver` doivent être en `running`.

---

## 2. Installer AWS CLI

> ℹ️ **Deux méthodes existent pour l'alias `s3minio` :**
> - **Recommandée (voir `README.md`)** : conteneur Docker `awscli` — zéro install,
>   marche dès `bash start.sh`. Les chemins locaux sont en `/data/` dans le conteneur.
> - **Alternative (ci-dessous)** : aws CLI installé en local — exécution plus
>   rapide, chemins hôte natifs (`~/data/`), mais installe un outil supplémentaire.
>
> Les commandes `s3minio ls`, `s3minio cp`… sont **identiques** dans les deux cas ;
> seul le backing change. Le README reste la référence ; cette section documente
> l'alternative pour ceux qui préfèrent un CLI natif.

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

## 4. Charger les datasets

```bash
pip install boto3 pandas pyarrow -q
python setup_datasets.py --endpoint http://localhost:9000

# Vérifier que le bucket existe
s3minio ls
```

---

## 5. Vérifier l'accès

```bash
s3minio ls s3://data-lake/
```

**Vous devriez voir** les datasets pré-chargés sous `raw/`.

| Interface | URL | Identifiants |
| --- | --- | --- |
| MinIO Console | <http://localhost:9001> | `minioadmin` / `minioadmin123` |
| Airflow UI | <http://localhost:8080> | `admin` / `admin` |

---

## 6. Adapter les commandes du TP

Dans les exercices qui mentionnent `[hidora-url]:9000`, remplacez par `localhost:9000`.
Le bucket à utiliser est `data-lake` (et non `data-lake-binome-XX`).

Les alias `s3minio` et `s3api` fonctionnent exactement de la même façon — seul l'endpoint change.

Pour Colab → MinIO local, le notebook doit tourner sur la même machine (Colab ne peut pas accéder à votre `localhost`). Utilisez les notebooks directement en local avec Jupyter :

```bash
pip install jupyter pyspark -q
jupyter notebook
```
