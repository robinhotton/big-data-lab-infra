# Création des utilisateurs — Serveur Hidora

> La création des utilisateurs est désormais **entièrement automatisée**.
> Ce document est conservé comme référence pour les opérations manuelles ponctuelles.

---

## Provisionnement automatique (recommandé)

```bash
# Depuis la racine du dépôt, en root
sudo bash formateur-start.sh
```

Ce script crée automatiquement :

- Les users Linux SSH (`binome01`..`binomeXX`)
- Les users MinIO avec policies IAM isolées
- Les users Airflow (rôle Viewer)
- Les fichiers `~/credentials.txt` dans chaque home
- Le symlink `~/dags/` vers le volume Airflow du binôme

Voir les URLs et identifiants dans [`connexion-hidora.md`](connexion-hidora.md).

---

## Opérations manuelles ponctuelles

### Re-provisionner uniquement les users (sans recharger les datasets)

```bash
sudo bash formateur-start.sh --skip-datasets
```

### Débloquer un binôme depuis root

```bash
su - binome01          # prendre la main
cat ~/credentials.txt  # voir ses credentials
```

### Ajouter un binôme en cours de session

```bash
# 1. Créer le bucket MinIO
docker compose -f docker-compose.yml run --rm awscli \
  s3 mb s3://data-lake-binome-09

# 2. Charger les datasets sur ce bucket
python3 setup_datasets.py \
  --endpoint http://localhost:9000 \
  --nb-binomes 1 \
  --prefix-bucket data-lake-binome-09

# 3. Créer le user SSH + MinIO + Airflow en ciblant NB_BINOMES=9
NB_BINOMES=9 sudo bash setup/create-ssh-users.sh
NB_BINOMES=9 bash setup/create-airflow-users.sh
# Pour MinIO, relancer create-minio-users.sh avec NB_BINOMES=9 via docker run
```

### Supprimer tous les utilisateurs (fin de formation)

```bash
for i in $(seq -f "%02g" 1 8); do
  userdel -r "binome${i}" 2>/dev/null || true
done
```

### Vérifier l'accès SSH par mot de passe (AlmaLinux 8.7)

```bash
grep PasswordAuthentication /etc/ssh/sshd_config
# Doit afficher : PasswordAuthentication yes
```
