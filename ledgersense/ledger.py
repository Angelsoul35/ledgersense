"""The double-entry ledger: a validated, append-only, tamper-evident journal.

Two invariants make this an accounting ledger rather than a list of numbers:

1. **Every entry balances.** Total debits equal total credits. An unbalanced
   entry is rejected, not posted.
2. **The journal is append-only and hash-chained.** Each posted entry stores a
   SHA-256 hash of its own content plus the previous entry's hash, so any later
   edit to a historical entry breaks every hash after it. :meth:`Ledger.verify`
   recomputes the chain and reports the first broken link.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .accounts import AccountType, ChartOfAccounts

GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class JournalLine:
    """One leg of an entry. Exactly one of ``debit``/``credit`` is non-zero."""

    account_code: str
    debit_cents: int = 0
    credit_cents: int = 0

    def __post_init__(self) -> None:
        if self.debit_cents < 0 or self.credit_cents < 0:
            raise ValueError("amounts must be non-negative")
        if bool(self.debit_cents) == bool(self.credit_cents):
            raise ValueError("a line must have exactly one of debit or credit, non-zero")


@dataclass
class JournalEntry:
    date: str  # ISO-8601 date, e.g. "2026-02-14"
    description: str
    lines: list[JournalLine]
    memo: str = ""
    # Assigned by the ledger at posting time:
    seq: int = -1
    entry_hash: str = ""
    prev_hash: str = ""

    @property
    def total_debits(self) -> int:
        return sum(line.debit_cents for line in self.lines)

    @property
    def total_credits(self) -> int:
        return sum(line.credit_cents for line in self.lines)

    @property
    def is_balanced(self) -> bool:
        return self.total_debits == self.total_credits and self.total_debits > 0

    def digest_payload(self) -> str:
        """Canonical JSON of the business content (excludes the hash fields)."""
        return json.dumps(
            {
                "seq": self.seq,
                "date": self.date,
                "description": self.description,
                "memo": self.memo,
                "lines": [
                    [line.account_code, line.debit_cents, line.credit_cents] for line in self.lines
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    def compute_hash(self) -> str:
        data = (self.prev_hash + self.digest_payload()).encode("utf-8")
        return hashlib.sha256(data).hexdigest()


@dataclass
class AccountBalance:
    code: str
    name: str
    type: AccountType
    debit_cents: int
    credit_cents: int

    @property
    def natural_cents(self) -> int:
        if self.type.is_debit_normal:
            return self.debit_cents - self.credit_cents
        return self.credit_cents - self.debit_cents


class UnbalancedEntryError(ValueError):
    pass


class Ledger:
    def __init__(self, chart: ChartOfAccounts) -> None:
        self.chart = chart
        self._entries: list[JournalEntry] = []

    @property
    def entries(self) -> list[JournalEntry]:
        return list(self._entries)

    @property
    def last_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else GENESIS_HASH

    def post(self, entry: JournalEntry) -> JournalEntry:
        """Validate and append an entry, chaining it to the journal head."""
        if not entry.is_balanced:
            raise UnbalancedEntryError(
                f"debits {entry.total_debits} != credits {entry.total_credits}"
            )
        for line in entry.lines:
            if line.account_code not in self.chart:
                raise KeyError(f"unknown account {line.account_code}")
        entry.seq = len(self._entries)
        entry.prev_hash = self.last_hash
        entry.entry_hash = entry.compute_hash()
        self._entries.append(entry)
        return entry

    def post_simple(
        self, date: str, description: str, debit: str, credit: str, cents: int, memo: str = ""
    ) -> JournalEntry:
        """Convenience for the common two-line entry (debit one, credit one)."""
        entry = JournalEntry(
            date=date,
            description=description,
            memo=memo,
            lines=[
                JournalLine(account_code=debit, debit_cents=cents),
                JournalLine(account_code=credit, credit_cents=cents),
            ],
        )
        return self.post(entry)

    def balances(self) -> list[AccountBalance]:
        debit: dict[str, int] = {}
        credit: dict[str, int] = {}
        for entry in self._entries:
            for line in entry.lines:
                debit[line.account_code] = debit.get(line.account_code, 0) + line.debit_cents
                credit[line.account_code] = credit.get(line.account_code, 0) + line.credit_cents
        out: list[AccountBalance] = []
        for account in self.chart.all():
            d = debit.get(account.code, 0)
            c = credit.get(account.code, 0)
            if d == 0 and c == 0:
                continue
            out.append(AccountBalance(account.code, account.name, account.type, d, c))
        return out

    def trial_balance(self) -> tuple[list[AccountBalance], int, int]:
        """Return (rows, total_debits, total_credits). The totals must be equal."""
        rows = self.balances()
        total_d = sum(r.debit_cents for r in rows)
        total_c = sum(r.credit_cents for r in rows)
        return rows, total_d, total_c

    def account_total(self, type: AccountType) -> int:
        return sum(b.natural_cents for b in self.balances() if b.type is type)

    def net_income_cents(self) -> int:
        return self.account_total(AccountType.INCOME) - self.account_total(AccountType.EXPENSE)

    def verify(self) -> tuple[bool, int]:
        """Recompute the hash chain. Returns (ok, first_broken_seq or -1)."""
        prev = GENESIS_HASH
        for entry in self._entries:
            expected_prev = prev
            recomputed = JournalEntry(
                date=entry.date,
                description=entry.description,
                lines=entry.lines,
                memo=entry.memo,
                seq=entry.seq,
                prev_hash=expected_prev,
            ).compute_hash()
            if entry.prev_hash != expected_prev or entry.entry_hash != recomputed:
                return False, entry.seq
            prev = entry.entry_hash
        return True, -1
