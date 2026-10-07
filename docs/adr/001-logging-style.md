# ADR-001 — Style de logging : `logger.info("%s", arg)` et non f-string

- **Statut** : Accepté
- **Date** : 2026-10-07
- **Décideur** : équipe pédagogique du lab Big Data
- **Contexte** : passage de `print()` à `logging` dans `airflow/src/` et le DAG
  `orders_pipeline` (V2.5)

---

## Contexte

Jusqu'à la V2.5, le code métier (`airflow/src/`) et les tâches du DAG
communiquaient par `print()`. Sous Airflow, un `print` :

- contourne le format de log des tâches (`task_context_logger`) ;
- ne peut pas être nivelé (`DEBUG` / `INFO` / `WARNING`) ni filtré ;
- ne peut pas être routé (remote logging S3, syslog, etc.).

D'où la migration vers `logging.getLogger(__name__)`. Restait à trancher
**la manière d'écrire les messages**.

## Décision

Dans le code métier et les DAGs, les messages sont écrits avec la
**lazy interpolation** de `logging` :

```python
logger.info("Bronze : %s événement(s) lus pour %s", len(events), ds)
```

et **jamais** avec un f-string ou une concaténation :

```python
# À ne pas faire dans le code de production
logger.info(f"Bronze : {len(events)} événement(s) lus pour {ds}")
```

Le module métier **ne configure aucun handler** : c'est Airflow (ou le
`__main__`, ou le runner de tests) qui le fait. Standard Python, zéro
dépendance.

### Exception assumée : les blocs `if __name__ == "__main__"`

Les `print()` restent autorisés dans les blocs de démonstration CLI de
`extract.py` et `transform.py`. Ce n'est pas du logging de production, c'est
de l'affichage console ponctuel — là où un `print` est plus naturel qu'un
logger sans handler configuré.

## Pourquoi — les trois options écartées

### Option A — f-string (écartée)

```python
logger.info(f"Bronze : {len(events)} événement(s) lus pour {ds}")
```

| Pour | Contre |
|---|---|
| Très lisible, idiome Python moderne | La chaîne est **construite à chaque appel**, même si le niveau de log est au-dessus et que le message sera jeté |
| Syntaxe déjà connue des apprenants | Perte des métadonnées de structure (les formatters `%` ne peuvent pas extraire les champs) |
| | Contredit la documentation Python et les linters (`flake8-logging-format` W1203, `pylint` W1203) |

Le point bloquant est le premier : dans `transform_silver` qui détaille
chaque événement rejeter, un f-string formate N chaînes pour n'en afficher
éventuellement aucune.

### Option B — `str.format()` (écartée)

```python
logger.info("Bronze : {} événement(s) lus pour {}".format(len(events), ds))
```

Même défaut que le f-string (interpolation immédiate), avec une syntaxe plus
verbeuse. Aucun avantage.

### Option C — concaténation (écartée)

```python
logger.info("Bronze : " + str(len(events)) + " événement(s)")
```

Illisible, et même problème d'interpolation immédiate.

### Option retenue — interpolation `%` lazy

```python
logger.info("Bronze : %s événement(s) lus pour %s", len(events), ds)
```

Les arguments restent **bruts** tant que le message n'est pas réellement émis.
Si le logger est en `INFO` et le message en `DEBUG`, rien n'est formaté : c'est
le mécanisme natif de `logging`, pas une optimisation maison.

Pour les messages à beaucoup d'arguments, la forme nommée est préférée :

```python
logger.info("Gold : %(n)s octets -> %(key)s", {"n": len(body), "key": key})
```

## Conséquences

**Positives**
- Les logs des tâches Airflow apparaissent au bon endroit, formés et filtrables.
- Zéro coût de formatage pour les messages filtrés — qui restent nombreux quand
  on passe en `DEBUG` pour diagnostiquer un apprenant.
- Les formatters `%` peuvent extraire les champs (utile pour un futur export
  structuré, type JSON).

**Négatives / limites**
- Syntaxe un peu moins familière pour un débutant qu'un f-string.
- L'apprenant qui copie `CODE/` du cours avec un `print` ne sera pas sanctionné :
  la règle s'applique au code qu'on maintient ici, pas à celui que l'apprenant écrit.
  Si le cours lui-même migre vers `logging`, l'ADR reste valide.

**Risques**
- Un contributeur peut réintroduire un f-string. Mitigation possible : ajouter
  `flake8-logging-format` à la CI. **Pas fait aujourd'hui** — jugé trop verbeux
  pour un lab ; à réévaluer si le dépôt est repris hors contexte formation.

## Comment appliquer la règle

Dans `airflow/src/` et `airflow/dags/` :

```python
import logging

logger = logging.getLogger(__name__)

# OK
logger.debug("event brut : %s", event)
logger.info("Silver : %s valides, %s -> quarantine", len(valid), len(invalid))
logger.warning("clé absente pour %s, ignorée", key)
logger.error("échec d'écriture pour %s : %s", key, exc)

# À éviter dans le code de production
logger.info(f"Silver : {len(valid)} valides")  # formatage immédiat
logger.info("Silver : %s" % len(valid))  # idem
logger.info("Silver : " + str(len(valid)))  # idem
```

Le bloc de démonstration reste libre :

```python
if __name__ == "__main__":
    print(f"Premier : {ev[0] if ev else 'vide'}")  # OK ici
```

## Références

- Documentation Python — [Logging HOWTO, « Formatting of final messages »](https://docs.python.org/3/howto/logging.html#optimization) : *« the most convenient way to format a message is to use the %s placeholder [...] the string is not formatted unless the message is actually logged »*
- [flake8-logging-format W1203](https://github.com/globality-corp/flake8-logging-format) — interpolation dans les messages de log
- [pylint W1203 `logging-fstring-interpolation`](https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/logging-fstring-interpolation.html)
- Convention Airflow : les opérateurs et hooks du framework utilisent `%s`, pas les f-strings

## Journal

| Date | Événement |
|---|---|
| 2026-10-07 | Décision actée à l'occasion de la V2.5 (`print` → `logging`). |
