"""Tests de airflow/src/transform.py — couche Silver (Python pur, sans pandas).

Alignés sur `CODE/transform.py` du cours et la nouvelle version lab. Couvre le
contrat de l'exo8 (deduplicate, compute_total_price, filter_valid_status,
validate_event) et l'idempotence du pipeline.
"""
from __future__ import annotations

from transform import (
    compute_total_price,
    deduplicate,
    filter_valid_status,
    transform_silver,
    validate_event,
)


def _event(event_id, status="completed", quantity=2, price=10.0):
    return {
        "event_id": event_id,
        "timestamp": "2026-03-01T10:00:00Z",
        "user_id": "u1",
        "product_id": "p1",
        "quantity": quantity,
        "price": price,
        "status": status,
    }


# --- deduplicate : garde le dernier event de chaque cle (idempotent) ---

def test_deduplicate_keeps_last_event():
    events = [
        _event("a1", status="pending", quantity=1, price=10.0),
        _event("a1", status="completed", quantity=1, price=10.0),
        _event("b2", status="completed", quantity=2, price=5.0),
    ]
    result = deduplicate(events, key="event_id")
    assert len(result) == 2
    a1 = next(e for e in result if e["event_id"] == "a1")
    assert a1["status"] == "completed"


def test_idempotence_two_runs_same_result():
    events = [
        _event("a1", quantity=1, price=10.0),
        _event("a2", status="pending", quantity=2, price=5.0),
        _event("a1", quantity=1, price=10.0),
    ]
    run1 = deduplicate(events)
    run2 = deduplicate(events)
    assert run1 == run2
    assert len(run1) == 2


# --- compute_total_price ---

def test_compute_total_price():
    assert compute_total_price({"quantity": 3, "price": 9.99}) == 29.97
    assert compute_total_price({"quantity": 1, "price": 0}) == 0.0


# --- filter_valid_status ---

def test_filter_valid_status_keeps_only_allowed():
    events = [
        {"event_id": "1", "status": "completed"},
        {"event_id": "2", "status": "BOGUS"},
        {"event_id": "3", "status": "pending"},
        {"event_id": "4", "status": "cancelled"},
        {"event_id": "5", "status": "refunded"},
    ]
    valid = filter_valid_status(events)
    assert len(valid) == 4
    assert all(e["status"] in {"pending", "completed", "cancelled", "refunded"} for e in valid)


# --- validate_event : contrat de donnees ---

def test_validate_event_ok():
    ok, reason = validate_event(_event("x1"))
    assert ok is True
    assert reason == ""


def test_validate_event_price_negative_rejected():
    ok, reason = validate_event(_event("x1", price=-5.0))
    assert ok is False
    assert "price" in reason


def test_validate_event_missing_field_rejected():
    e = {"event_id": "x1", "quantity": 2, "price": 10.0}
    ok, reason = validate_event(e)
    assert ok is False


def test_validate_event_bad_status_rejected():
    ok, reason = validate_event(_event("x1", status="BOGUS"))
    assert ok is False
    assert "status" in reason


# --- transform_silver : pipeline complet valide/dedup/total_price ---

def test_transform_silver_splits_valid_and_invalid():
    events = [
        _event("a1", quantity=2, price=10.0, status="completed"),
        _event("b2", price=-5.0),
    ]
    valid, invalid = transform_silver(events)
    assert len(valid) == 1
    assert valid[0]["total_price"] == 20.0
    assert len(invalid) == 1
    assert "_reject_reason" in invalid[0]
