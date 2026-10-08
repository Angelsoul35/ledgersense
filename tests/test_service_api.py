from __future__ import annotations

from fastapi.testclient import TestClient

from ledgersense.main import app

client = TestClient(app)


def test_categorize_endpoint():
    r = client.post("/categorize", json={"description": "monthly cloud hosting invoice"})
    assert r.status_code == 200
    body = r.json()
    assert body["account_code"] == "6100"
    assert 0.0 <= body["confidence"] <= 1.0


def test_expense_and_trial_balance_flow():
    # A confident charge posts and keeps the books balanced.
    r = client.post(
        "/expense",
        json={"date": "2026-03-01", "description": "office lease payment", "cents": 150_000},
    )
    assert r.status_code == 200
    assert r.json()["posted"] is True

    tb = client.get("/trial-balance").json()
    assert tb["balanced"] is True
    assert tb["total_debits"] == tb["total_credits"]


def test_verify_endpoint():
    r = client.get("/verify")
    assert r.status_code == 200
    assert r.json()["intact"] is True
