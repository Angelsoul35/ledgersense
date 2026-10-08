from __future__ import annotations

import pytest

from ledgersense.accounts import AccountType
from ledgersense.ledger import JournalEntry, JournalLine, Ledger, UnbalancedEntryError


def test_balanced_entry_posts(ledger: Ledger):
    entry = ledger.post_simple("2026-01-01", "Owner capital", "1000", "3000", 100_000)
    assert entry.seq == 0
    assert entry.is_balanced
    assert entry.entry_hash
    assert entry.prev_hash == "0" * 64


def test_unbalanced_entry_rejected(ledger: Ledger):
    bad = JournalEntry(
        date="2026-01-01",
        description="broken",
        lines=[
            JournalLine("1000", debit_cents=100),
            JournalLine("3000", credit_cents=90),
        ],
    )
    with pytest.raises(UnbalancedEntryError):
        ledger.post(bad)


def test_line_requires_exactly_one_side():
    with pytest.raises(ValueError):
        JournalLine("1000", debit_cents=10, credit_cents=10)
    with pytest.raises(ValueError):
        JournalLine("1000")  # both zero
    with pytest.raises(ValueError):
        JournalLine("1000", debit_cents=-5)


def test_unknown_account_rejected(ledger: Ledger):
    with pytest.raises(KeyError):
        ledger.post_simple("2026-01-01", "typo", "9999", "3000", 100)


def test_trial_balance_always_balances(ledger: Ledger):
    ledger.post_simple("2026-01-01", "capital", "1000", "3000", 500_000)
    ledger.post_simple("2026-01-02", "rent", "6000", "1000", 120_000)
    ledger.post_simple("2026-01-03", "sale", "1000", "4000", 230_000)
    _rows, total_d, total_c = ledger.trial_balance()
    assert total_d == total_c


def test_net_income(ledger: Ledger):
    ledger.post_simple("2026-01-01", "sale", "1000", "4000", 300_000)
    ledger.post_simple("2026-01-02", "rent", "6000", "1000", 120_000)
    assert ledger.account_total(AccountType.INCOME) == 300_000
    assert ledger.account_total(AccountType.EXPENSE) == 120_000
    assert ledger.net_income_cents() == 180_000


def test_hash_chain_detects_tampering(ledger: Ledger):
    ledger.post_simple("2026-01-01", "capital", "1000", "3000", 500_000)
    ledger.post_simple("2026-01-02", "rent", "6000", "1000", 120_000)
    ledger.post_simple("2026-01-03", "sale", "1000", "4000", 230_000)
    ok, broken = ledger.verify()
    assert ok and broken == -1

    # Quietly edit a historical entry: verification must fail at that seq.
    ledger._entries[1].lines[0] = JournalLine("6000", debit_cents=999_999)
    ok, broken = ledger.verify()
    assert not ok
    assert broken == 1
