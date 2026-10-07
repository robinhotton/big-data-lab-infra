# ADR-001 — Logging : `%s` lazy, pas de f-string

- **Statut** : Accepté
- **Date** : 2026-10-07
- **Suite** : migration `print` → `logging` (V2.5)

## Décision

```python
logger.info("Bronze : %s événement(s) lus pour %s", len(events), ds)  # retenu
logger.info(f"Bronze : {len(events)} événement(s) lus pour {ds}")  # interdit
```

Exception : les `print()` restent OK dans les blocs `if __name__ == "__main__"` (démos CLI).

## Pourquoi

Un f-string est formaté **à chaque appel**, même si le message est filtré. La formule `%s` ne l'est que si le log est réellement émis — mécanisme natif de `logging`, pas une optimisation maison.

Impact réel : `transform_silver` détaille chaque événement rejeté. Avec un f-string, on construit N chaînes pour n'en afficher souvent aucune.

Les f-strings fonctionnent ; ce sont aussi ce que flaggent la doc Python, `flake8-logging-format` (W1203) et `pylint` (W1203), et la convention Airflow est au `%s`.

## Conséquences

- Logs de tâches Airflow formés, filtrables, sans coût sur les niveaux désactivés.
- Syntaxe moins familière pour un débutant qu'un f-string — c'est le prix.
- Pas de garde anti-régression en CI (W1203 non ajouté) : jugé trop strict pour un lab.

## Références

- [Logging HOWTO — Optimization](https://docs.python.org/3/howto/logging.html#optimization)
- [flake8-logging-format W1203](https://github.com/globality-corp/flake8-logging-format) · `pylint` W1203
