"""Functional tests for the real-transaction benchmark.

These check behaviour, not surface: the loader returns the real vendored rows
with their exact counts and classes, the shipped categoriser beats the
chance/majority baselines on genuinely held-out data, the verdict is well-fit,
shuffled labels collapse the score to the baseline, and the network fetch path
parses ClassLabels, pages, retries and merges splits — all through a
monkeypatched ``urlopen`` so no test touches the network.
"""

from __future__ import annotations

import json
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse

import pytest

from ledgersense.real_benchmark import (
    OVERFIT,
    UNDERFIT,
    WELL_FIT,
    _decide,
    benchmark,
)
from ledgersense.real_data import (
    CATEGORIES,
    DATASET,
    RealTransaction,
    dedupe,
    fetch_rows,
    fetch_split,
    load_real_data,
    load_records,
    vendor_dataset,
)

# A handful of memos known to be in the real dataset, with their true labels.
# If the loader ever returned something other than the real vendored rows (a
# stub, a shuffle, a wrong column), these exact pairings would break.
KNOWN_MEMOS = {
    "Uber 072515 SFPOOL": "Transportation",
    "INTRST PYMNT": "Payments/Credits",
    "Starbucks": "Dining Out",
    "SparkFun": "Shopping",
}


@pytest.fixture(scope="module")
def report():
    return benchmark()


# --------------------------------------------------------------------------- #
# Loader: the real vendored data, exact counts and classes.
# --------------------------------------------------------------------------- #
def test_loader_returns_the_real_dataset():
    texts, labels = load_real_data()
    assert len(texts) == 282
    assert len(labels) == 282
    assert sorted(set(labels)) == list(CATEGORIES)
    assert len(set(labels)) == 8


def test_loader_contains_known_real_memos():
    texts, labels = load_real_data()
    pairs = dict(zip(texts, labels, strict=True))
    for memo, category in KNOWN_MEMOS.items():
        assert memo in pairs, f"{memo!r} missing from vendored data"
        assert pairs[memo] == category


def test_records_merge_both_splits():
    records = load_records()
    splits = [r.split for r in records]
    assert splits.count("train") == 225
    assert splits.count("test") == 57
    assert len(records) == 282


def test_dedupe_drops_exact_duplicate_rows():
    texts, labels = load_real_data()
    dx, dy = dedupe(texts, labels)
    assert len(dx) == 231
    assert len(dx) < len(texts)  # duplicates really were present
    pairs = list(zip(dx, dy, strict=True))
    assert len(set(pairs)) == len(pairs)  # no exact (text, label) duplicate remains


# --------------------------------------------------------------------------- #
# Benchmark: generalisation beats the baselines; verdict; control.
# --------------------------------------------------------------------------- #
def test_benchmark_shapes_are_consistent(report):
    assert report.n_vendored == 282
    assert report.n_examples == 231
    assert report.n_classes == 8
    assert len(report.cv_accuracy_folds) == report.cv_folds == 5
    assert report.chance == pytest.approx(1 / 8)
    assert report.majority_baseline == pytest.approx(report.majority_baseline)


def test_beats_chance_and_majority_on_holdout(report):
    # Far above both trivial baselines on data unseen at fit time.
    assert report.majority_baseline < 0.2  # the data really is near-uniform
    assert report.holdout_test_accuracy > report.majority_baseline + 0.3
    assert report.holdout_test_accuracy > report.chance * 3
    # Macro-F1 (unweighted over classes) also clears the majority rate, so the
    # score is not an artefact of guessing the biggest class.
    assert report.holdout_test_macro_f1 > report.majority_baseline + 0.3


def test_cross_validation_beats_majority_and_is_stable(report):
    assert report.cv_accuracy > report.majority_baseline + 0.3
    assert report.cv_macro_f1 > report.majority_baseline + 0.3
    assert report.lift_over_majority > 3.0
    assert report.cv_accuracy_std <= 0.15  # folds agree; not one lucky split


def test_training_saturates_but_generalises(report):
    # A high-capacity linear model memorises a few hundred short memos: train is
    # near-perfect. That is capacity, not the verdict driver.
    assert report.holdout_train_accuracy >= 0.95
    assert report.train_test_gap > 0.0


def test_verdict_is_well_fit(report):
    assert report.verdict == WELL_FIT
    assert "generalises" in report.rationale


def test_shuffled_labels_collapse_to_baseline(report):
    # Destroying the text->category link must destroy the score.
    assert report.shuffled_cv_accuracy <= report.majority_baseline + 0.05
    assert report.shuffled_cv_accuracy < report.cv_accuracy - 0.3


def test_report_str_is_readable(report):
    text = str(report)
    assert "WELL-FIT" in text
    assert "cross-validation" in text
    assert "shuffled-label control" in text


# --------------------------------------------------------------------------- #
# The verdict rule itself: the overfit and underfit branches.
# --------------------------------------------------------------------------- #
def test_decide_well_fit():
    verdict, _ = _decide(
        cv_accuracy=0.62,
        cv_accuracy_std=0.08,
        holdout_train_accuracy=0.99,
        holdout_test_accuracy=0.71,
        shuffled_cv_accuracy=0.14,
        majority_baseline=0.16,
    )
    assert verdict == WELL_FIT


def test_decide_underfit_when_training_not_learned():
    verdict, reason = _decide(
        cv_accuracy=0.15,
        cv_accuracy_std=0.05,
        holdout_train_accuracy=0.40,  # cannot even fit training
        holdout_test_accuracy=0.14,
        shuffled_cv_accuracy=0.13,
        majority_baseline=0.16,
    )
    assert verdict == UNDERFIT
    assert "too low" in reason


def test_decide_overfit_when_generalisation_fails():
    verdict, reason = _decide(
        cv_accuracy=0.22,  # barely above the 2x = 0.32 margin -> fails it
        cv_accuracy_std=0.05,
        holdout_train_accuracy=0.99,  # fits training perfectly
        holdout_test_accuracy=0.25,
        shuffled_cv_accuracy=0.15,
        majority_baseline=0.16,
    )
    assert verdict == OVERFIT
    assert "generalisation is weak" in reason


def test_decide_overfit_when_control_does_not_collapse():
    # Strong held-out but shuffled labels still score high -> it is fitting an
    # artefact, not signal. Must not be called well-fit.
    verdict, _ = _decide(
        cv_accuracy=0.62,
        cv_accuracy_std=0.08,
        holdout_train_accuracy=0.99,
        holdout_test_accuracy=0.71,
        shuffled_cv_accuracy=0.55,  # control failed to collapse
        majority_baseline=0.16,
    )
    assert verdict == OVERFIT


# --------------------------------------------------------------------------- #
# Fetch path: parsing, ClassLabel resolution, paging, retries, merge — all with
# a monkeypatched urlopen, so no network is touched.
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._data = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False


_NAMES = ["Transportation", "Dining Out", "Shopping"]


def _page_payload(split: str, offset: int, length: int, rows_by_split: dict) -> dict:
    rows = rows_by_split[split]
    page = rows[offset : offset + length]
    return {
        "features": [
            {"feature_idx": 0, "name": "merchant", "type": {"dtype": "string", "_type": "Value"}},
            {
                "feature_idx": 1,
                "name": "category",
                "type": {"names": _NAMES, "_type": "ClassLabel"},
            },
        ],
        "rows": [
            {"row_idx": offset + i, "row": {"merchant": text, "category": label}}
            for i, (text, label) in enumerate(page)
        ],
        "num_rows_total": len(rows),
        "num_rows_per_page": length,
        "partial": False,
    }


def _make_urlopen(rows_by_split: dict):
    """A urlopen that serves pages from an in-memory dataset and records calls."""
    calls: list[str] = []

    def urlopen(request, timeout=None):
        url = request.full_url
        calls.append(url)
        query = parse_qs(urlparse(url).query)
        assert query["dataset"][0] == DATASET
        split = query["split"][0]
        offset = int(query["offset"][0])
        length = int(query["length"][0])
        return _FakeResponse(_page_payload(split, offset, length, rows_by_split))

    urlopen.calls = calls  # type: ignore[attr-defined]
    return urlopen


def test_fetch_rows_parses_payload():
    urlopen = _make_urlopen({"train": [("Uber", 0), ("KFC", 1)]})
    payload = fetch_rows("train", 0, 100, urlopen=urlopen)
    assert payload["num_rows_total"] == 2
    assert payload["rows"][0]["row"]["merchant"] == "Uber"


def test_fetch_split_resolves_classlabels():
    # Labels arrive as ClassLabel ints and must be resolved to names.
    rows = {"train": [("Uber", 0), ("KFC", 1), ("SparkFun", 2)]}
    urlopen = _make_urlopen(rows)
    records = fetch_split("train", urlopen=urlopen)
    assert [r.category for r in records] == ["Transportation", "Dining Out", "Shopping"]
    assert [r.text for r in records] == ["Uber", "KFC", "SparkFun"]
    assert all(r.split == "train" for r in records)


def test_fetch_split_pages_through_multiple_requests(monkeypatch):
    import ledgersense.real_data as rd

    monkeypatch.setattr(rd, "_PAGE", 2)
    rows = {"train": [("Uber", 0), ("KFC", 1), ("SparkFun", 2)]}
    urlopen = _make_urlopen(rows)
    records = rd.fetch_split("train", urlopen=urlopen)
    assert len(records) == 3
    assert len(urlopen.calls) == 2  # two pages fetched


def test_fetch_dataset_merges_splits(monkeypatch):
    import ledgersense.real_data as rd

    monkeypatch.setattr(rd, "SPLITS", ("train", "test"))
    rows = {"train": [("Uber", 0), ("KFC", 1)], "test": [("SparkFun", 2)]}
    urlopen = _make_urlopen(rows)
    records = rd.fetch_dataset(urlopen=urlopen)
    assert len(records) == 3
    assert [r.split for r in records] == ["train", "train", "test"]
    assert records[-1].category == "Shopping"


def test_fetch_rows_retries_then_succeeds():
    attempts = {"n": 0}
    good = _make_urlopen({"train": [("Uber", 0)]})
    slept: list[float] = []

    def flaky(request, timeout=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise URLError("temporary blip")
        return good(request, timeout=timeout)

    payload = fetch_rows("train", urlopen=flaky, retries=3, sleep=slept.append)
    assert attempts["n"] == 2  # failed once, succeeded on retry
    assert slept == [2.0]  # one backoff of backoff * 2**0
    assert payload["num_rows_total"] == 1


def test_fetch_rows_exhausts_retries_and_raises():
    slept: list[float] = []

    def always_fails(request, timeout=None):
        raise URLError("down")

    with pytest.raises(RuntimeError, match="could not fetch"):
        fetch_rows("train", urlopen=always_fails, retries=3, backoff=1.0, sleep=slept.append)
    assert slept == [1.0, 2.0]  # retries - 1 backoffs, exponential


def test_fetch_split_rejects_non_classlabel_category():
    # A payload whose category column is a plain Value, not a ClassLabel, cannot
    # be resolved to names and must fail loudly rather than mislabel.
    def urlopen(request, timeout=None):
        return _FakeResponse(
            {
                "features": [
                    {"name": "merchant", "type": {"dtype": "string", "_type": "Value"}},
                    {"name": "category", "type": {"dtype": "int64", "_type": "Value"}},
                ],
                "rows": [{"row_idx": 0, "row": {"merchant": "Uber", "category": 0}}],
                "num_rows_total": 1,
            }
        )

    with pytest.raises(ValueError, match="not a ClassLabel"):
        fetch_split("train", urlopen=urlopen)


def test_load_records_skips_blank_lines(tmp_path):
    path = tmp_path / "with_blanks.jsonl"
    path.write_text(
        json.dumps({"text": "Uber", "category": "Transportation", "split": "train"})
        + "\n\n"  # a stray blank line must be ignored
        + json.dumps({"text": "KFC", "category": "Dining Out", "split": "test"})
        + "\n",
        encoding="utf-8",
    )
    records = load_records(path)
    assert records == [
        RealTransaction("Uber", "Transportation", "train"),
        RealTransaction("KFC", "Dining Out", "test"),
    ]


def test_vendor_dataset_round_trips(tmp_path):
    rows = {"train": [("Uber", 0), ("KFC", 1)], "test": [("SparkFun", 2)]}
    urlopen = _make_urlopen(rows)
    out = tmp_path / "vendored.jsonl"

    import ledgersense.real_data as rd

    # Confine SPLITS to the two we provide for this isolated fetch.
    original_splits = rd.SPLITS
    rd.SPLITS = ("train", "test")
    try:
        vendor_dataset(out, urlopen=urlopen)
    finally:
        rd.SPLITS = original_splits

    loaded = load_records(out)
    assert loaded == [
        RealTransaction("Uber", "Transportation", "train"),
        RealTransaction("KFC", "Dining Out", "train"),
        RealTransaction("SparkFun", "Shopping", "test"),
    ]
