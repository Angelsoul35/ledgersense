from __future__ import annotations

from ledgersense.anomaly import detect
from ledgersense.ledger import Ledger


def _seed_normal_software(ledger: Ledger) -> None:
    for i, cents in enumerate([49_00, 55_00, 60_00, 68_00, 75_00, 82_00]):
        ledger.post_simple(f"2026-01-0{i+1}", "saas", "6100", "1000", cents)


def test_detects_amount_outlier(ledger: Ledger):
    _seed_normal_software(ledger)
    ledger.post_simple("2026-01-20", "huge saas bill", "6100", "1000", 9_400_00)
    found = detect(ledger, z_threshold=3.5, min_cents=1000, min_samples=5)
    assert any(a.account_code == "6100" and a.amount_cents == 9_400_00 for a in found)
    top = found[0]
    assert top.robust_z > 3.5
    assert "6100" in top.account_code


def test_too_few_samples_is_not_flagged(ledger: Ledger):
    # Only two postings: not enough history to call anything anomalous.
    ledger.post_simple("2026-01-01", "saas", "6100", "1000", 50_00)
    ledger.post_simple("2026-01-02", "huge", "6100", "1000", 9_000_00)
    assert detect(ledger, min_samples=5) == []


def test_identical_amounts_have_no_anomaly(ledger: Ledger):
    for i in range(6):
        ledger.post_simple(f"2026-02-0{i+1}", "rent", "6000", "1000", 120_000)
    assert detect(ledger, min_samples=5) == []
