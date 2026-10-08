"""Application service: ties the categoriser, the ledger and the anomaly check together."""

from __future__ import annotations

from dataclasses import dataclass

from .accounts import default_chart
from .anomaly import AmountAnomaly, detect
from .categorizer import Suggestion, TransactionCategorizer
from .config import Settings, get_settings
from .ledger import JournalEntry, Ledger


@dataclass
class RecordedExpense:
    suggestion: Suggestion
    posted: bool
    entry: JournalEntry | None
    note: str


class LedgerService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.ledger = Ledger(default_chart())
        self.categorizer = TransactionCategorizer(
            min_confidence=self.settings.categoriser_min_confidence
        ).fit()

    def categorize(self, description: str) -> Suggestion:
        return self.categorizer.suggest(description)

    def record_expense(
        self, date: str, description: str, cents: int, paid_from: str = "1000"
    ) -> RecordedExpense:
        """Categorise a spend and, if confident, post it as a debit to the
        suggested account and a credit to the funding account (cash by default).

        A low-confidence suggestion is *not* auto-posted; it is returned for a
        human to confirm. Guessing silently is how bad bookkeeping happens.
        """
        suggestion = self.categorize(description)
        if suggestion.needs_review:
            return RecordedExpense(
                suggestion=suggestion,
                posted=False,
                entry=None,
                note="confidence below threshold; routed to manual review",
            )
        entry = self.ledger.post_simple(
            date=date,
            description=description,
            debit=suggestion.account_code,
            credit=paid_from,
            cents=cents,
            memo=f"auto-categorised (p={suggestion.confidence:.2f})",
        )
        return RecordedExpense(
            suggestion=suggestion,
            posted=True,
            entry=entry,
            note=f"posted to {suggestion.account_code} {suggestion.account_name}",
        )

    def anomalies(self) -> list[AmountAnomaly]:
        return detect(
            self.ledger,
            z_threshold=self.settings.anomaly_z_threshold,
            min_cents=self.settings.anomaly_min_cents,
        )
