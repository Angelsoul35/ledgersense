"""Statistical anomaly detection over posted amounts, per account.

The categoriser answers *which account*; this module answers *does this amount
look normal for that account*. It uses a **robust z-score** built on the median
and the median absolute deviation (MAD), not the mean and standard deviation, so
a single huge outlier cannot inflate the spread and hide itself. The rule is
deterministic and explainable: a bookkeeper sees the amount, the account's
typical range, and how many robust standard deviations away the posting is.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .accounts import AccountType
from .ledger import Ledger

# Amount-anomaly detection is only meaningful where a single account's postings
# are expected to be of a similar size. Expense and income categories qualify (a
# "software" line is usually tens of euros; a huge one stands out). Asset,
# liability and equity accounts — above all a cash/clearing account — aggregate
# heterogeneous flows (capital injections, sales, every payment), so their
# amounts are legitimately all over the place and flagging them is just noise.
_DEFAULT_TYPES = (AccountType.EXPENSE, AccountType.INCOME)

# 0.6745 scales the MAD so that, for normally distributed data, the robust
# z-score matches the ordinary z-score.
_MAD_TO_SIGMA = 0.6745


@dataclass
class AmountAnomaly:
    seq: int
    date: str
    account_code: str
    account_name: str
    amount_cents: int
    robust_z: float
    median_cents: int
    reason: str


def _amounts_by_account(ledger: Ledger) -> dict[str, list[tuple[int, int, str]]]:
    """Map account_code -> list of (amount_cents, entry_seq, date) for its postings."""
    by_account: dict[str, list[tuple[int, int, str]]] = {}
    for entry in ledger.entries:
        for line in entry.lines:
            amount = line.debit_cents + line.credit_cents
            by_account.setdefault(line.account_code, []).append(
                (amount, entry.seq, entry.date)
            )
    return by_account


def detect(
    ledger: Ledger,
    *,
    z_threshold: float = 3.5,
    min_cents: int = 1000,
    min_samples: int = 5,
    account_types: tuple[AccountType, ...] = _DEFAULT_TYPES,
) -> list[AmountAnomaly]:
    """Flag postings whose amount is a robust-z outlier for their account.

    Only accounts whose type is in ``account_types`` are considered (expense and
    income by default — see the note at the top of this module). Accounts with
    fewer than ``min_samples`` postings are skipped: there is not enough history
    to call anything anomalous, and guessing would be dishonest.
    """
    anomalies: list[AmountAnomaly] = []
    for code, rows in _amounts_by_account(ledger).items():
        if ledger.chart.get(code).type not in account_types:
            continue
        amounts = np.array([r[0] for r in rows], dtype=float)
        if len(amounts) < min_samples:
            continue
        median = float(np.median(amounts))
        mad = float(np.median(np.abs(amounts - median)))
        if mad == 0.0:
            continue  # all postings identical; no meaningful spread
        account = ledger.chart.get(code)
        for amount, seq, date in rows:
            if amount < min_cents:
                continue
            robust_z = _MAD_TO_SIGMA * (amount - median) / mad
            if abs(robust_z) >= z_threshold:
                direction = "above" if robust_z > 0 else "below"
                anomalies.append(
                    AmountAnomaly(
                        seq=seq,
                        date=date,
                        account_code=code,
                        account_name=account.name,
                        amount_cents=amount,
                        robust_z=round(robust_z, 2),
                        median_cents=int(median),
                        reason=(
                            f"{amount / 100:.2f} is {abs(robust_z):.1f} robust SD "
                            f"{direction} the usual {median / 100:.2f} for {account.name}"
                        ),
                    )
                )
    return sorted(anomalies, key=lambda a: abs(a.robust_z), reverse=True)
