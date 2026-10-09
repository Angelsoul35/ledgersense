"""Fetcher and loader for a real, public transaction-categorisation dataset.

The dataset is ``rajeshradhakrishnan/fin-transaction-category`` on the Hugging
Face Hub: real bank/card transaction memos — ``"Uber 072515 SFPOOL"``,
``"INTRST PYMNT"``, ``"Starbucks"`` — each labelled with one of eight spending
categories. It is pulled through the public *datasets-server* rows API, which
needs no authentication and returns the ``category`` column as a **ClassLabel**:
an integer index into a list of names. The fetcher resolves those integers back
to the category strings, merges the ``train`` and ``test`` splits, and vendors
the result as JSONL under ``datasets/`` so the benchmark runs offline and the
exact bytes evaluated are versioned in the repository.

The network layer takes an injectable ``urlopen`` and retries transient failures
with exponential backoff, so the fetch path is deterministic under test and
resilient against the occasional ``502`` from the public API.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

DATASET = "rajeshradhakrishnan/fin-transaction-category"
CONFIG = "default"
SPLITS = ("train", "test")

_ROWS_API = "https://datasets-server.huggingface.co/rows"
_TEXT_FIELD = "merchant"
_LABEL_FIELD = "category"
_PAGE = 100
_USER_AGENT = "ledgersense/1.0 (dataset fetch; +https://github.com/Angelsoul35/ledgersense)"

# The eight ClassLabel names shipped by the dataset, in sorted order. Exposed so
# callers (and tests) can assert the label space without a network round-trip.
CATEGORIES: tuple[str, ...] = (
    "Dining Out",
    "Entertainment",
    "Housing",
    "Payments/Credits",
    "Service Subscriptions",
    "Shopping",
    "Transportation",
    "Utilities",
)

# Where the vendored copy lives (repo-root/datasets/...), independent of cwd.
DATA_PATH = Path(__file__).resolve().parent.parent / "datasets" / "fin_transaction_category.jsonl"

UrlOpen = Callable[..., object]


@dataclass(frozen=True)
class RealTransaction:
    """One labelled, real transaction memo and the split it came from."""

    text: str
    category: str
    split: str


def _rows_url(split: str, offset: int, length: int) -> str:
    query = urlencode(
        {"dataset": DATASET, "config": CONFIG, "split": split, "offset": offset, "length": length}
    )
    return f"{_ROWS_API}?{query}"


def fetch_rows(
    split: str,
    offset: int = 0,
    length: int = _PAGE,
    *,
    urlopen: UrlOpen = urllib.request.urlopen,
    retries: int = 4,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = 60.0,
) -> dict:
    """Fetch one page of the rows API, retrying transient network errors.

    ``urlopen`` and ``sleep`` are injectable so the network path is exercised
    deterministically in tests. Retries use exponential backoff (``backoff`` ·
    2**attempt seconds); the final failure is re-raised wrapped in a
    :class:`RuntimeError` that names the URL.
    """
    url = _rows_url(split, offset, length)
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last_error = exc
            if attempt < retries - 1:
                sleep(backoff * (2**attempt))
    raise RuntimeError(f"could not fetch {url} after {retries} attempts") from last_error


def _resolve_label_names(payload: dict) -> list[str]:
    """Pull the ClassLabel name list out of a rows-API payload's ``features``."""
    for feature in payload.get("features", []):
        if feature.get("name") == _LABEL_FIELD:
            feature_type = feature.get("type", {})
            if feature_type.get("_type") == "ClassLabel":
                return list(feature_type["names"])
    raise ValueError(f"{_LABEL_FIELD!r} is not a ClassLabel in the dataset features")


def fetch_split(
    split: str, *, urlopen: UrlOpen = urllib.request.urlopen, **kwargs
) -> list[RealTransaction]:
    """Fetch and page through one split, resolving ClassLabel ints to names."""
    first = fetch_rows(split, 0, _PAGE, urlopen=urlopen, **kwargs)
    names = _resolve_label_names(first)
    total = int(first["num_rows_total"])
    raw = list(first["rows"])
    offset = _PAGE
    while offset < total:
        raw.extend(fetch_rows(split, offset, _PAGE, urlopen=urlopen, **kwargs)["rows"])
        offset += _PAGE

    records: list[RealTransaction] = []
    for item in raw:
        row = item["row"]
        label = row[_LABEL_FIELD]
        category = names[int(label)] if isinstance(label, int) else str(label)
        records.append(
            RealTransaction(text=str(row[_TEXT_FIELD]).strip(), category=category, split=split)
        )
    return records


def fetch_dataset(*, urlopen: UrlOpen = urllib.request.urlopen, **kwargs) -> list[RealTransaction]:
    """Fetch every configured split and return the merged list of records."""
    records: list[RealTransaction] = []
    for split in SPLITS:
        records.extend(fetch_split(split, urlopen=urlopen, **kwargs))
    return records


def write_jsonl(records: Sequence[RealTransaction], path: Path | str = DATA_PATH) -> Path:
    """Write records to JSONL (one object per line) and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(
                json.dumps(
                    {"text": record.text, "category": record.category, "split": record.split},
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def vendor_dataset(
    path: Path | str = DATA_PATH, *, urlopen: UrlOpen = urllib.request.urlopen
) -> Path:
    """Fetch the live dataset and write the vendored JSONL copy. Regenerates the
    file under ``datasets/``; run it to refresh the vendored data from source."""
    return write_jsonl(fetch_dataset(urlopen=urlopen), path)


def load_records(path: Path | str = DATA_PATH) -> list[RealTransaction]:
    """Load the vendored dataset exactly as stored (both splits, every row)."""
    path = Path(path)
    records: list[RealTransaction] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            records.append(
                RealTransaction(text=obj["text"], category=obj["category"], split=obj["split"])
            )
    return records


def load_real_data(path: Path | str = DATA_PATH) -> tuple[list[str], list[str]]:
    """Return ``(texts, categories)`` for every vendored row, in file order."""
    records = load_records(path)
    return [r.text for r in records], [r.category for r in records]


def dedupe(texts: Sequence[str], labels: Sequence[str]) -> tuple[list[str], list[str]]:
    """Drop exact ``(text, label)`` duplicates, preserving first-seen order.

    Identical memos appearing in both the train and test splits would otherwise
    leak across a train/test boundary; removing exact duplicates makes the
    benchmark's splits leakage-free while keeping every genuinely distinct
    example (including the one memo that carries two different real labels).
    """
    seen: set[tuple[str, str]] = set()
    kept_texts: list[str] = []
    kept_labels: list[str] = []
    for text, label in zip(texts, labels, strict=False):
        key = (text, label)
        if key in seen:
            continue
        seen.add(key)
        kept_texts.append(text)
        kept_labels.append(label)
    return kept_texts, kept_labels


if __name__ == "__main__":  # pragma: no cover
    written = vendor_dataset()
    print(f"vendored {len(load_records(written))} rows to {written}")
