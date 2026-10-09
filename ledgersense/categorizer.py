"""An explainable transaction categoriser: free-text description -> account code.

A ``FeatureUnion`` of a word view (1-2 grams, phrasing) and a character view
(``char_wb`` 3-5, which survives abbreviations and typos) feeds a logistic
regression. Linear by design, so every suggestion comes with the words that
drove it — a bookkeeper can see *why* a charge was mapped to an account and
override it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

from .accounts import default_chart
from .generate import make_dataset


@dataclass
class Suggestion:
    account_code: str
    account_name: str
    confidence: float
    needs_review: bool
    top_terms: list[tuple[str, float]]


def _build_features() -> FeatureUnion:
    return FeatureUnion(
        [
            ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)),
        ]
    )


def build_pipeline() -> Pipeline:
    """The categoriser's exact learning pipeline as an unfitted scikit-learn estimator.

    This is the single source of truth for the model: :meth:`TransactionCategorizer.fit`
    trains an instance of it, and any external evaluation (for example
    :mod:`ledgersense.real_benchmark`) measures *this* pipeline rather than a
    stand-in, so the reported numbers describe the component that ships.
    """
    return Pipeline(
        [
            ("features", _build_features()),
            ("clf", LogisticRegression(max_iter=2000, C=4.0)),
        ]
    )


class TransactionCategorizer:
    def __init__(self, min_confidence: float = 0.45) -> None:
        self.min_confidence = min_confidence
        self._pipeline: Pipeline | None = None
        self._chart = default_chart()

    def fit(self, texts: list[str] | None = None, labels: list[str] | None = None):
        if texts is None or labels is None:
            texts, labels = make_dataset()
        pipeline = build_pipeline()
        pipeline.fit(texts, labels)
        self._pipeline = pipeline
        return self

    def _require_fitted(self) -> Pipeline:
        if self._pipeline is None:
            raise RuntimeError("categoriser is not fitted; call fit() first")
        return self._pipeline

    def suggest(self, description: str) -> Suggestion:
        pipeline = self._require_fitted()
        clf: LogisticRegression = pipeline.named_steps["clf"]
        proba = pipeline.predict_proba([description])[0]
        best = int(np.argmax(proba))
        code = str(clf.classes_[best])
        confidence = float(proba[best])
        try:
            name = self._chart.get(code).name
        except KeyError:
            name = code
        return Suggestion(
            account_code=code,
            account_name=name,
            confidence=confidence,
            needs_review=confidence < self.min_confidence,
            top_terms=self._explain(pipeline, description, best),
        )

    def _explain(
        self, pipeline: Pipeline, description: str, class_index: int, k: int = 5
    ) -> list[tuple[str, float]]:
        features: FeatureUnion = pipeline.named_steps["features"]
        clf: LogisticRegression = pipeline.named_steps["clf"]
        x = features.transform([description])
        names = features.get_feature_names_out()
        coef = clf.coef_[class_index] if clf.coef_.shape[0] > 1 else clf.coef_[0]
        contributions = x.multiply(coef).toarray()[0]
        order = np.argsort(contributions)[::-1]
        out: list[tuple[str, float]] = []
        for idx in order[:k]:
            if contributions[idx] <= 0:
                break
            raw = str(names[idx])
            term = raw.split("__", 1)[1] if "__" in raw else raw
            out.append((term, round(float(contributions[idx]), 4)))
        return out
