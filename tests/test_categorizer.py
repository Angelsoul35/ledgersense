from __future__ import annotations

import pytest

from ledgersense.categorizer import TransactionCategorizer
from ledgersense.evaluation import phrase_disjoint_eval


def test_unfitted_raises():
    with pytest.raises(RuntimeError):
        TransactionCategorizer().suggest("anything")


def test_suggests_sensible_accounts(categorizer: TransactionCategorizer):
    cases = {
        "monthly cloud hosting invoice for the servers": "6100",
        "flight and hotel for the client conference": "6200",
        "quarterly office lease payment": "6000",
        "electricity and water utility bill": "6300",
        "consulting fee received from the client": "4100",
    }
    for text, expected in cases.items():
        s = categorizer.suggest(text)
        assert s.account_code == expected, f"{text!r} -> {s.account_code}, expected {expected}"
        assert s.top_terms  # explanation populated


def test_anchor_disjoint_generalises_without_overfitting():
    # Leakage-free evaluation: whole anchor keywords are held out of training, so the
    # test vocabulary is unseen and a near-1.0 within-distribution score cannot
    # hide memorisation. Measured ~0.89 +/- 0.04 across seeds.
    report = phrase_disjoint_eval()
    assert report.accuracy >= 0.78  # nine classes; chance is ~0.11
    assert report.train_accuracy >= 0.95
    assert report.gap <= 0.22  # bounded -> learns the stem signal, not templates


def test_low_confidence_is_flagged_for_review():
    clf = TransactionCategorizer(min_confidence=0.99).fit()
    # With an impossibly high threshold, even a clear charge needs review.
    s = clf.suggest("monthly cloud hosting invoice")
    assert s.needs_review
