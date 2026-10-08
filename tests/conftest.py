from __future__ import annotations

import pytest

from ledgersense.accounts import default_chart
from ledgersense.categorizer import TransactionCategorizer
from ledgersense.ledger import Ledger


@pytest.fixture(scope="session")
def categorizer() -> TransactionCategorizer:
    # Fitting trains the TF-IDF + logistic pipeline once for the whole session.
    return TransactionCategorizer().fit()


@pytest.fixture
def ledger() -> Ledger:
    return Ledger(default_chart())
