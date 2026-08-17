# Connexion Hidora — Formation Big Data

> **Ce fichier est la référence unique des endpoints distants.**
> Les supports de cours utilisent des placeholders génériques (`[hidora-url]:9000` etc.).
> Remplacez-les par les valeurs ci-dessous.

Instance : `node199038-iso-big-data-cloud.sh1.hidora.com`

---

## Correspondance placeholders → ports réels

| Placeholder dans les supports | Endpoint réel Hidora |
| --- | --- |
| `http://[hidora-url]:9000` | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11700` |
| `http://[hidora-url]:9001` | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11701` |
| `http://[hidora-url]:8080` | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11702` |
| `[hidora-url]` (SSH) | `node199038-iso-big-data-cloud.sh1.hidora.com` port `11717` |

---

## Accès apprenants (SSH)

```bash
ssh binomeXX@node199038-iso-big-data-cloud.sh1.hidora.com -p 11717
# Password : Diginamic34_
```

| Binôme | User SSH | Bucket MinIO |
| --- | --- | --- |
| 01 | `binome01` | `data-lake-binome-01` |
| 02 | `binome02` | `data-lake-binome-02` |
| … | … | … |
| 08 | `binome11` | `data-lake-binome-11` |

---

## URLs des services

| Service | URL | Identifiants |
| --- | --- | --- |
| SSH | `node199038-iso-big-data-cloud.sh1.hidora.com:11717` | `binomeXX` / `Diginamic34_` |
| MinIO API (S3) | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11700` | — |
| MinIO Console | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11701` | `binomeXX` / `Diginamic34_` |
| Airflow UI | `http://node199038-iso-big-data-cloud.sh1.hidora.com:11702` | `binomeXX` / `Diginamic34_` |

> **Admin formateur** : MinIO → `minioadmin` / `minioadmin123`  —  Airflow → `admin` / `admin`

---

## Déployer un DAG depuis son poste (TP3)

Les apprenants déposent leurs DAGs via SCP — Airflow les détecte en < 1 min :

```bash
scp -P 11717 orders_pipeline_dag.py binomeXX@node199038-iso-big-data-cloud.sh1.hidora.com:~/dags/
```

---

## Mise à jour si l'URL Hidora change

1. Modifier `.env` : mettre à jour `HIDORA_HOST` et les ports
2. Relancer `sudo bash formateur-start.sh --skip-datasets` pour re-provisionner users et credentials

---

## Dépannage SSH

**L'authentification par mot de passe est-elle activée ?**

```bash
grep PasswordAuthentication /etc/ssh/sshd_config
# Doit afficher : PasswordAuthentication yes
# Sinon :
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
systemctl restart sshd
```

**Débloquer un binôme depuis root :**

```bash
su - binomeXX       # prendre la main sur la session du binôme
cat credentials.txt # voir ses credentials
```
