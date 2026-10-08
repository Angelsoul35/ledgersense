"""Command-line demo and entry point."""

from __future__ import annotations

import sys

from .accounts import AccountType
from .service import LedgerService


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def demo() -> None:
    svc = LedgerService()
    ledger = svc.ledger

    print("LedgerSense demo\n" + "=" * 60)

    # 1) Opening balances and some ordinary business activity.
    print("\n1) Posting opening capital and recurring activity ...")
    ledger.post_simple("2026-01-01", "Owner investment", "1000", "3000", 5_000_00)
    ledger.post_simple("2026-01-02", "January office rent", "6000", "1000", 1_200_00)
    ledger.post_simple("2026-01-05", "Product sales week 1", "1000", "4000", 2_300_00)
    ledger.post_simple("2026-01-12", "Product sales week 2", "1000", "4000", 1_950_00)

    # Several software charges so the anomaly detector has a baseline to learn.
    software_charges = [
        ("2026-01-03", "monthly SaaS subscription renewal", 49_00),
        ("2026-01-06", "cloud hosting and compute invoice", 82_00),
        ("2026-01-09", "developer tool subscription payment", 60_00),
        ("2026-01-15", "recurring API plan charge", 75_00),
        ("2026-01-18", "productivity suite seat renewal", 55_00),
        ("2026-01-21", "online platform subscription fee", 68_00),
        ("2026-01-24", "annual software license billed to the card", 9_400_00),  # outlier
    ]

    print("\n2) Auto-categorising free-text charges ...")
    for date, text, cents in software_charges:
        r = svc.record_expense(date, text, cents)
        flag = "" if r.posted else "  [NEEDS REVIEW]"
        terms = ", ".join(t for t, _ in r.suggestion.top_terms[:3])
        print(
            f"   {_money(cents):>12}  -> {r.suggestion.account_code} "
            f"{r.suggestion.account_name:<22} p={r.suggestion.confidence:.2f}{flag}"
        )
        print(f"                 why: {terms}")

    # A travel charge, to show the categoriser crosses account types correctly.
    r = svc.record_expense("2026-01-27", "hotel stay during the conference", 320_00)
    print(
        f"   {_money(32000):>12}  -> {r.suggestion.account_code} "
        f"{r.suggestion.account_name:<22} p={r.suggestion.confidence:.2f}"
    )

    # 3) Trial balance.
    print("\n3) Trial balance (debits must equal credits):")
    rows, total_d, total_c = ledger.trial_balance()
    for row in rows:
        print(
            f"   {row.code}  {row.name:<24} "
            f"D {_money(row.debit_cents):>12}  C {_money(row.credit_cents):>12}"
        )
    print(f"   {'':<30} D {_money(total_d):>12}  C {_money(total_c):>12}")
    print(f"   balanced: {total_d == total_c}")

    # 4) Income statement summary.
    income = ledger.account_total(AccountType.INCOME)
    expense = ledger.account_total(AccountType.EXPENSE)
    print("\n4) Income statement:")
    print(f"   revenue      {_money(income):>14}")
    print(f"   expenses     {_money(expense):>14}")
    print(f"   net income   {_money(ledger.net_income_cents()):>14}")

    # 5) Anomaly detection.
    print("\n5) Amount anomalies (robust z-score per account):")
    found = svc.anomalies()
    if not found:
        print("   none")
    for a in found:
        print(f"   seq {a.seq} [{a.account_code}] z={a.robust_z}: {a.reason}")

    # 6) Tamper-evidence.
    print("\n6) Tamper-evidence of the journal:")
    ok, broken = ledger.verify()
    print(f"   chain intact before tampering: {ok} (broken seq: {broken})")
    victim = ledger._entries[2]
    original = victim.description
    victim.description = "Product sales week 1 (quietly altered)"
    ok, broken = ledger.verify()
    print(f"   after editing entry seq 2:     {ok} (broken seq: {broken})")
    victim.description = original
    ok, broken = ledger.verify()
    print(f"   after restoring the entry:     {ok} (broken seq: {broken})")


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "demo":
        demo()
        return 0
    print("usage: python -m ledgersense.cli demo")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
