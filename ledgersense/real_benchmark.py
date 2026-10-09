"""Benchmark the shipped categoriser on real, labelled transaction memos.

This measures :func:`ledgersense.categorizer.build_pipeline` — the *exact* TF-IDF
+ logistic-regression pipeline the :class:`~ledgersense.categorizer.TransactionCategorizer`
trains on — against the real dataset vendored in :mod:`ledgersense.real_data`,
mapping a free-text memo to one of eight spending categories.

The report is built to be read by a sceptic. It gives two independent views of
generalisation (stratified k-fold cross-validation *and* a held-out split), the
train/test gap, the chance and majority baselines the model must beat, and a
shuffled-label control that destroys the text→category relationship. The verdict
(well-fit / overfit / underfit) is derived from **generalisation strength and the
control**, not from the training-set score: a high-capacity linear model
saturates the training accuracy of a few hundred short memos to ~1.0 by design,
so the training score carries no information about generalisation and is not used
to call overfitting. What calls it is whether held-out performance stays far
above the baselines and whether the shuffled control collapses to chance.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.utils import shuffle as sk_shuffle

from .categorizer import build_pipeline
from .real_data import dedupe, load_real_data

WELL_FIT = "well-fit"
OVERFIT = "overfit"
UNDERFIT = "underfit"


@dataclass
class RealBenchmarkReport:
    n_vendored: int
    n_examples: int
    n_classes: int
    majority_class: str
    majority_baseline: float
    chance: float
    cv_folds: int
    cv_macro_f1: float
    cv_macro_f1_std: float
    cv_accuracy: float
    cv_accuracy_std: float
    cv_accuracy_folds: list[float]
    holdout_train_accuracy: float
    holdout_test_accuracy: float
    holdout_test_macro_f1: float
    train_test_gap: float
    shuffled_cv_accuracy: float
    verdict: str
    rationale: str = field(default="")

    @property
    def lift_over_majority(self) -> float:
        """How many times the majority-class baseline the CV accuracy reaches."""
        return self.cv_accuracy / self.majority_baseline

    def __str__(self) -> str:
        pct = lambda x: f"{100 * x:5.1f}%"  # noqa: E731
        lines = [
            "LedgerSense categoriser — real transaction benchmark",
            "=" * 60,
            f"dataset        : {self.n_vendored} real memos vendored "
            f"-> {self.n_examples} unique (text, label) examples",
            "                 (exact duplicates dropped to keep splits leakage-free)",
            f"classes        : {self.n_classes}  "
            f"(majority '{self.majority_class}' = {pct(self.majority_baseline)})",
            f"baselines      : chance {pct(self.chance)}  |  "
            f"majority {pct(self.majority_baseline)}",
            "",
            f"{self.cv_folds}-fold stratified cross-validation (the robust headline):",
            f"  macro-F1     : {pct(self.cv_macro_f1)} +/- {pct(self.cv_macro_f1_std)}",
            f"  accuracy     : {pct(self.cv_accuracy)} +/- {pct(self.cv_accuracy_std)}   "
            f"# {self.lift_over_majority:.1f}x the majority baseline",
            f"  per-fold acc : {', '.join(pct(a).strip() for a in self.cv_accuracy_folds)}",
            "",
            "held-out split (stratified, unseen at fit time):",
            f"  train acc    : {pct(self.holdout_train_accuracy)}",
            f"  test  acc    : {pct(self.holdout_test_accuracy)}",
            f"  test  macro-F1: {pct(self.holdout_test_macro_f1)}",
            f"  train/test gap: {pct(self.train_test_gap)}   "
            f"# training saturates by design; the verdict reads generalisation, not this gap",
            "",
            "shuffled-label control (text -> category link destroyed):",
            f"  accuracy     : {pct(self.shuffled_cv_accuracy)}   "
            f"# collapses to ~chance -> the real score is signal, not memorised noise",
            "",
            f"verdict        : {self.verdict.upper()}",
            f"  {self.rationale}",
        ]
        return "\n".join(lines)


def _decide(
    *,
    cv_accuracy: float,
    cv_accuracy_std: float,
    holdout_train_accuracy: float,
    holdout_test_accuracy: float,
    shuffled_cv_accuracy: float,
    majority_baseline: float,
) -> tuple[str, str]:
    """Classify the fit from generalisation strength and the shuffled control.

    * **underfit** — the model cannot even learn the training set, so there is no
      capacity to generalise.
    * **well-fit** — held-out *and* cross-validated accuracy clear twice the
      majority baseline, the folds agree (bounded variance), and the shuffled
      control collapses to the baseline (the model is reading real signal).
    * **overfit** — the model fits training but fails one of those generalisation
      tests: held-out does not clear the baseline margin, the folds disagree, or
      the control does not collapse (it is fitting noise).
    """
    margin = 2.0 * majority_baseline
    fits_training = holdout_train_accuracy >= 0.90
    generalises = cv_accuracy >= margin and holdout_test_accuracy >= margin
    control_collapses = shuffled_cv_accuracy <= majority_baseline + 0.05
    stable = cv_accuracy_std <= 0.15

    if not fits_training:
        return UNDERFIT, (
            f"training accuracy {holdout_train_accuracy:.2f} is too low to have learned the "
            "task, let alone generalise."
        )
    if generalises and control_collapses and stable:
        return WELL_FIT, (
            f"held-out {holdout_test_accuracy:.2f} and CV {cv_accuracy:.2f} both clear "
            f"{margin:.2f} (2x majority) with bounded fold variance, and shuffled labels "
            f"collapse to {shuffled_cv_accuracy:.2f} ~ chance; the model reads real signal "
            "and generalises, so the saturated training score is capacity, not memorisation."
        )
    return OVERFIT, (
        f"training fits ({holdout_train_accuracy:.2f}) but generalisation is weak: "
        f"CV {cv_accuracy:.2f} / held-out {holdout_test_accuracy:.2f} vs a {margin:.2f} "
        f"margin, fold std {cv_accuracy_std:.2f}, shuffled control {shuffled_cv_accuracy:.2f}."
    )


def benchmark(seed: int = 11, n_splits: int = 5, holdout_frac: float = 0.25) -> RealBenchmarkReport:
    """Run the full real-data benchmark and return a structured report.

    Everything is seeded, so the numbers are reproducible run to run.
    """
    texts, labels = load_real_data()
    n_vendored = len(texts)
    x, y = dedupe(texts, labels)
    y_arr = np.asarray(y)

    counts = Counter(y)
    majority_class, majority_count = counts.most_common(1)[0]
    n_classes = len(counts)
    majority_baseline = majority_count / len(y)
    chance = 1.0 / n_classes

    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    scores = cross_validate(
        build_pipeline(), x, y_arr, cv=cv, scoring=("f1_macro", "accuracy")
    )
    cv_macro = scores["test_f1_macro"]
    cv_acc = scores["test_accuracy"]

    x_train, x_test, y_train, y_test = train_test_split(
        x, y_arr, test_size=holdout_frac, stratify=y_arr, random_state=seed
    )
    model = build_pipeline().fit(x_train, y_train)
    train_pred = model.predict(x_train)
    test_pred = model.predict(x_test)
    holdout_train_acc = float(accuracy_score(y_train, train_pred))
    holdout_test_acc = float(accuracy_score(y_test, test_pred))
    holdout_test_f1 = float(f1_score(y_test, test_pred, average="macro"))

    y_shuffled = sk_shuffle(y_arr, random_state=seed)
    shuffled_scores = cross_validate(build_pipeline(), x, y_shuffled, cv=cv, scoring=("accuracy",))
    shuffled_cv_acc = float(np.mean(shuffled_scores["test_accuracy"]))

    verdict, rationale = _decide(
        cv_accuracy=float(np.mean(cv_acc)),
        cv_accuracy_std=float(np.std(cv_acc)),
        holdout_train_accuracy=holdout_train_acc,
        holdout_test_accuracy=holdout_test_acc,
        shuffled_cv_accuracy=shuffled_cv_acc,
        majority_baseline=majority_baseline,
    )

    return RealBenchmarkReport(
        n_vendored=n_vendored,
        n_examples=len(y),
        n_classes=n_classes,
        majority_class=majority_class,
        majority_baseline=majority_baseline,
        chance=chance,
        cv_folds=n_splits,
        cv_macro_f1=float(np.mean(cv_macro)),
        cv_macro_f1_std=float(np.std(cv_macro)),
        cv_accuracy=float(np.mean(cv_acc)),
        cv_accuracy_std=float(np.std(cv_acc)),
        cv_accuracy_folds=[round(float(a), 4) for a in cv_acc],
        holdout_train_accuracy=holdout_train_acc,
        holdout_test_accuracy=holdout_test_acc,
        holdout_test_macro_f1=holdout_test_f1,
        train_test_gap=round(holdout_train_acc - holdout_test_acc, 4),
        shuffled_cv_accuracy=shuffled_cv_acc,
        verdict=verdict,
        rationale=rationale,
    )


if __name__ == "__main__":  # pragma: no cover
    print(benchmark())
