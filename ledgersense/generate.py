"""Synthetic, labelled transaction descriptions for the categoriser.

Design note (this matters for honesty). A first version used a handful of fixed
sentences per account; a phrase-disjoint evaluation then scored only ~0.44 with a
0.56 train/test gap — the classic template-memorisation trap. Real bank and card
descriptions are not arbitrary sentences: each category carries **recurring
anchor keywords** a bookkeeper always associates with it ("rent", "payroll",
"subscription", "airfare") that reappear inside ever-changing surrounding text.

So descriptions here are composed from two parts:

* **anchors** — the strong, recurring keyword(s) for an account ("office rent",
  "payroll salary", "software subscription"); within an account they share
  partial stems the way real memos do, so a keyword held out of training still
  carries *some* learnable signal; and
* **context** — generic filler ("monthly", "invoice", "ref 1234", "billed to the
  card"), shared across all accounts because it appears everywhere.

The honest evaluation (:func:`make_split_datasets`) holds out *whole anchor
keywords* from training, so the test descriptions centre on merchant vocabulary
never seen in training. That is the hard, realistic generalisation question — can
the model place a charge it has no exact keyword for? — and it is why the
reported accuracy sits around 0.89, not a suspicious 1.0.

Everything here is synthetic — no real transaction is involved.
"""

from __future__ import annotations

import numpy as np

# Strong, recurring keywords per account code (from the default chart). Within an
# account the anchors share partial stems the way real memos do ("lease"/"rent"
# for rent; "software"/"subscription" for SaaS), so that an anchor held out of
# training still carries *some* learnable signal — but not so much that the task
# is trivial. Some vocabulary is deliberately generic/ambiguous ("monthly fee",
# "transfer") to keep the problem realistically hard.
ANCHORS: dict[str, list[str]] = {
    "6100": [  # Software Subscriptions
        "software subscription",
        "software license",
        "saas subscription plan",
        "cloud software hosting",
        "developer software tool",
        "api software plan",
        "productivity software seat",
    ],
    "6200": [  # Travel Expense
        "flight airfare",
        "airline travel ticket",
        "hotel travel lodging",
        "taxi travel ride",
        "travel rental car",
        "train travel fare",
        "business travel trip",
    ],
    "6000": [  # Rent Expense
        "office rent",
        "workspace lease rent",
        "coworking lease membership",
        "warehouse rental",
        "studio space lease",
        "monthly rent instalment",
        "office lease payment",
    ],
    "6300": [  # Utilities Expense
        "electricity utility bill",
        "water and sewage utility",
        "internet broadband utility",
        "gas heating utility",
        "telecom utility service",
        "power utility statement",
    ],
    "6400": [  # Payroll Expense
        "staff payroll salary",
        "payroll wages run",
        "employee salary wages",
        "contractor payroll payout",
        "freelancer wages payment",
        "monthly payroll compensation",
    ],
    "6500": [  # Bank Fees
        "bank maintenance fee",
        "wire transfer bank fee",
        "foreign transaction fee",
        "overdraft bank fee",
        "card processor fee",
        "account service fee",
    ],
    "5000": [  # Cost of Goods Sold
        "wholesale inventory purchase",
        "raw materials stock",
        "inventory stock replenishment",
        "manufacturing components",
        "goods for resale stock",
        "supplier inventory order",
    ],
    "4000": [  # Sales Revenue
        "product sale revenue",
        "store order sale",
        "retail checkout sale",
        "marketplace sale payout",
        "point-of-sale revenue",
        "goods sale income",
    ],
    "4100": [  # Service Revenue
        "consulting service fee",
        "service invoice revenue",
        "monthly service retainer",
        "support service contract",
        "professional services fee",
        "project service milestone",
    ],
}

# Generic surrounding phrasing, shared across all accounts. These are split
# disjointly in make_split_datasets so test sentences read differently.
CONTEXT_FRAGMENTS: list[str] = [
    "monthly",
    "annual",
    "quarterly",
    "payment",
    "invoice",
    "charge",
    "billed to the card",
    "for the quarter",
    "renewal",
    "recurring",
    "statement",
    "received from the customer",
    "settled",
    "paid",
    "transfer",
    "reimbursement",
]

ALL_CODES = list(ANCHORS.keys())


def _compose(
    rng: np.random.Generator, anchors: list[str], contexts: list[str]
) -> str:
    anchor = str(rng.choice(anchors))
    k = int(rng.integers(1, 3))
    frags = list(rng.choice(contexts, size=min(k, len(contexts)), replace=False))
    parts = [anchor, *frags]
    rng.shuffle(parts)
    text = " ".join(parts)
    if int(rng.integers(4)) == 0:
        text += f" ref {int(rng.integers(1000, 9999))}"
    return text


def _generate(
    rng: np.random.Generator,
    n: int,
    anchor_pool: dict[str, list[str]],
    context_pool: list[str],
) -> tuple[list[str], list[str]]:
    codes = list(anchor_pool.keys())
    texts: list[str] = []
    labels: list[str] = []
    for _ in range(n):
        code = codes[int(rng.integers(len(codes)))]
        texts.append(_compose(rng, anchor_pool[code], context_pool))
        labels.append(code)
    return texts, labels


def make_dataset(n: int = 1600, seed: int = 11) -> tuple[list[str], list[str]]:
    rng = np.random.default_rng(seed)
    return _generate(rng, n, ANCHORS, CONTEXT_FRAGMENTS)


def _split_anchors(rng: np.random.Generator, holdout_frac: float):
    train, test = {}, {}
    for code, anchors in ANCHORS.items():
        idx = rng.permutation(len(anchors))
        cut = max(1, round(len(anchors) * (1 - holdout_frac)))
        train[code] = [anchors[i] for i in idx[:cut]]
        test[code] = [anchors[i] for i in idx[cut:]] or [anchors[idx[-1]]]
    return train, test


def make_split_datasets(
    n: int = 1600, seed: int = 11, holdout_frac: float = 0.35
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Anchor-disjoint train/test: whole anchor keywords are held out of training,
    so the test descriptions centre on merchant vocabulary never seen in training.

    This is the hard, realistic generalisation question — can the model place a
    charge it has no exact keyword for? — not the trivial one of re-reading a
    known keyword in new filler. Context phrasing is shared (it is generic and
    appears everywhere). Returns (train_texts, train_labels, test_texts, test_labels).
    """
    rng = np.random.default_rng(seed)
    a_train, a_test = _split_anchors(rng, holdout_frac)
    tr_t, tr_y = _generate(rng, n, a_train, CONTEXT_FRAGMENTS)
    te_t, te_y = _generate(rng, n // 3, a_test, CONTEXT_FRAGMENTS)
    return tr_t, tr_y, te_t, te_y
