"""transform.py — Code métier Silver (Python pur, sans pandas ni Spark).

Version *lab* de `CODE/transform.py` du cours (cours-big-data_local-2j). Mêmes
contrats : `deduplicate`, `compute_total_price`, `filter_valid_status`,
`validate_event`, `transform_silver`. Utilisée par exo8, TP2 et le DAG.

Bronze → Silver : validation (contract de données), déduplication idempotente,
filtrage des status autorisés, calcul de `total_price = quantity * price`.
Testable hors Airflow (cf. `tests/airflow_src/test_transform.py`).

Colonnes orders (dataset du lab) :
  event_id, timestamp, user_id, product_id, quantity, price, status
"""
from __future__ import annotations

from datetime import datetime, timezone

VALID_STATUSES = {"pending", "completed", "cancelled", "refunded"}


def deduplicate(events: list[dict], key: str = "event_id") -> list[dict]:
    """Déduplication idempotente : on garde le DERNIER événement de chaque clé.

    On parcourt la liste et on écrase dans un dict indexé par la clé → le dernier
    gagne. Re-déclencher le pipeline sur les mêmes données produit le même résultat,
    sans doublon : c'est ça, l'idempotence.
    """
    by_key: dict[str, dict] = {}
    for e in events:
        val = e.get(key)
        if val is not None:
            by_key[val] = e  # écrase : le dernier gagne
    return list(by_key.values())


def compute_total_price(event: dict) -> float:
    """`total_price = quantity * price`, arrondi à 2 décimales."""
    return round(float(event["quantity"]) * float(event["price"]), 2)


def filter_valid_status(events: list[dict]) -> list[dict]:
    """Garde uniquement les événements dont le `status` est autorisé."""
    return [e for e in events if e.get("status") in VALID_STATUSES]


def validate_event(event: dict) -> tuple[bool, str]:
    """Valide un événement contre le contrat de données.

    Retourne `(True, "")` si valide, `(False, "raison")` sinon.
    Équivalent Python pur des checks qualité du CRS 06.
    """
    required = {"event_id", "timestamp", "user_id", "quantity", "price", "status"}
    missing = required - set(event.keys())
    if missing:
        return False, f"champs manquants : {sorted(missing)}"

    for col in ("event_id", "timestamp", "user_id"):
        if event.get(col) is None:
            return False, f"{col} est null"

    try:
        price = float(event["price"])
        qty = int(event["quantity"])
    except (ValueError, TypeError):
        return False, "price/quantity non numériques"

    if price <= 0:
        return False, f"price <= 0 ({price})"
    if qty < 1:
        return False, f"quantity < 1 ({qty})"

    if event["status"] not in VALID_STATUSES:
        return False, f"status invalide : {event['status']}"

    return True, ""


def transform_silver(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pipeline Silver complet : valide, déduplique, ajoute `total_price`.

    Retourne `(valides_avec_total_price, invalides_annotés)`.
    Les invalides partent en quarantaine (cf. `load.write_quarantine`).
    """
    valid, invalid = [], []
    for e in events:
        ok, reason = validate_event(e)
        if ok:
            valid.append(e)
        else:
            invalid.append({
                **e,
                "_reject_reason": reason,
                "_reject_ts": datetime.now(timezone.utc).isoformat(),
            })

    valid = deduplicate(valid)
    valid = filter_valid_status(valid)
    for e in valid:
        e["total_price"] = compute_total_price(e)

    return valid, invalid


if __name__ == "__main__":
    # Démonstration hors Airflow (testable directement)
    sample = [
        {"event_id": "a1", "timestamp": "2026-03-01T10:00:00Z",
         "user_id": "u1", "product_id": "p1", "quantity": 2, "price": 10.0,
         "status": "completed"},
        {"event_id": "a1", "timestamp": "2026-03-01T10:05:00Z",  # doublon -> écrasé
         "user_id": "u1", "product_id": "p1", "quantity": 3, "price": 10.0,
         "status": "completed"},
        {"event_id": "b2", "timestamp": "2026-03-01T11:00:00Z",
         "user_id": "u2", "product_id": "p2", "quantity": 1, "price": -5.0,  # KO
         "status": "completed"},
    ]
    valid, invalid = transform_silver(sample)
    print(f"Valides   : {len(valid)}")
    for e in valid:
        print(f"  {e['event_id']}  total_price={e['total_price']}  status={e['status']}")
    print(f"Invalides : {len(invalid)}")
    for e in invalid:
        print(f"  {e.get('event_id', '?')}  raison={e['_reject_reason']}")
