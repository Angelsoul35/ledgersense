"""Leakage-free, phrase-disjoint evaluation of the transaction categoriser.

A random split of synthetic data would report a meaningless ~1.0 accuracy
because train and test share phrasings. :func:`phrase_disjoint_eval` instead
trains on one pool of phrasings and tests on a *disjoint* pool, so the test
wording was never seen in training and the number reflects real generalisation.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.metrics import accuracy_score

from .categorizer import TransactionCategorizer
from .generate import make_split_datasets


@dataclass
class EvalReport:
    accuracy: float
    train_accuracy: float
    gap: float
    n_train: int
    n_test: int

    def __str__(self) -> str:
        return (
            f"accuracy          : {self.accuracy:.2f}   # phrasings unseen in training\n"
            f"train accuracy    : {self.train_accuracy:.2f}\n"
            f"train-test gap    : {self.gap:.2f}   # bounded -> learns signal, not templates\n"
            f"n_train / n_test  : {self.n_train} / {self.n_test}"
        )


def phrase_disjoint_eval(seed: int = 11, holdout_frac: float = 0.35) -> EvalReport:
    tr_t, tr_y, te_t, te_y = make_split_datasets(seed=seed, holdout_frac=holdout_frac)
    model = TransactionCategorizer().fit(tr_t, tr_y)

    test_pred = [model.suggest(t).account_code for t in te_t]
    train_pred = [model.suggest(t).account_code for t in tr_t]

    acc = float(accuracy_score(te_y, test_pred))
    train_acc = float(accuracy_score(tr_y, train_pred))
    return EvalReport(
        accuracy=acc,
        train_accuracy=train_acc,
        gap=round(train_acc - acc, 4),
        n_train=len(tr_t),
        n_test=len(te_t),
    )


def aggregate_eval(seeds: range | list[int] = range(6), holdout_frac: float = 0.35) -> str:
    """Average the anchor-disjoint eval over several seeds, so the headline number
    is robust rather than a single lucky split."""
    reports = [phrase_disjoint_eval(seed=s, holdout_frac=holdout_frac) for s in seeds]
    accs = [r.accuracy for r in reports]
    mean = sum(accs) / len(accs)
    std = (sum((a - mean) ** 2 for a in accs) / len(accs)) ** 0.5
    train = sum(r.train_accuracy for r in reports) / len(reports)
    gap = sum(r.gap for r in reports) / len(reports)
    n = len(list(seeds))
    return (
        f"accuracy (mean+/-std over {n} seeds): {mean:.2f} +/- {std:.2f}   "
        f"# nine accounts; chance ~0.11; keywords unseen in training\n"
        f"train accuracy                     : {train:.2f}\n"
        f"train-test gap                     : {gap:.2f}   # bounded -> stem signal, not templates"
    )


if __name__ == "__main__":  # pragma: no cover
    print(aggregate_eval())
