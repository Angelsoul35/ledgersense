"""Chart of accounts and the accounting identities behind double-entry.

Amounts everywhere in LedgerSense are integer **cents**. Money is never a float:
``0.1 + 0.2 != 0.3`` in binary floating point, and a ledger that cannot add its
own numbers is worthless. Cents (``int``) are exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountType(StrEnum):
    """The five classical account types and their *normal* balance side.

    Assets and expenses increase on the **debit** side; liabilities, equity and
    income increase on the **credit** side. This single fact drives every
    balance calculation in the ledger.
    """

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"

    @property
    def is_debit_normal(self) -> bool:
        return self in (AccountType.ASSET, AccountType.EXPENSE)


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: AccountType

    def natural_balance(self, debit_cents: int, credit_cents: int) -> int:
        """Signed balance on the account's *natural* side.

        A positive number means the account carries the balance you would
        expect (an asset with money in it, a revenue account that earned).
        """
        if self.type.is_debit_normal:
            return debit_cents - credit_cents
        return credit_cents - debit_cents


class ChartOfAccounts:
    """An ordered collection of accounts keyed by a short code (e.g. ``1000``)."""

    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}

    def add(self, code: str, name: str, type: AccountType) -> Account:
        if code in self._accounts:
            raise ValueError(f"account {code} already exists")
        account = Account(code=code, name=name, type=type)
        self._accounts[code] = account
        return account

    def get(self, code: str) -> Account:
        try:
            return self._accounts[code]
        except KeyError:
            raise KeyError(f"unknown account {code}") from None

    def __contains__(self, code: object) -> bool:
        return code in self._accounts

    def by_type(self, type: AccountType) -> list[Account]:
        return [a for a in self._accounts.values() if a.type is type]

    def all(self) -> list[Account]:
        return list(self._accounts.values())


def default_chart() -> ChartOfAccounts:
    """A small but realistic small-business chart of accounts."""
    coa = ChartOfAccounts()
    coa.add("1000", "Cash", AccountType.ASSET)
    coa.add("1100", "Accounts Receivable", AccountType.ASSET)
    coa.add("1500", "Equipment", AccountType.ASSET)
    coa.add("2000", "Accounts Payable", AccountType.LIABILITY)
    coa.add("2100", "Sales Tax Payable", AccountType.LIABILITY)
    coa.add("3000", "Owner's Equity", AccountType.EQUITY)
    coa.add("4000", "Sales Revenue", AccountType.INCOME)
    coa.add("4100", "Service Revenue", AccountType.INCOME)
    coa.add("5000", "Cost of Goods Sold", AccountType.EXPENSE)
    coa.add("6000", "Rent Expense", AccountType.EXPENSE)
    coa.add("6100", "Software Subscriptions", AccountType.EXPENSE)
    coa.add("6200", "Travel Expense", AccountType.EXPENSE)
    coa.add("6300", "Utilities Expense", AccountType.EXPENSE)
    coa.add("6400", "Payroll Expense", AccountType.EXPENSE)
    coa.add("6500", "Bank Fees", AccountType.EXPENSE)
    return coa
