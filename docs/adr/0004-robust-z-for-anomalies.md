# ADR 0004 — Use a robust z-score for amount anomalies

## Status
Accepted.

## Context
We want to flag postings whose amount is unusual for their account. The obvious
approach — mean and standard deviation — has a well-known flaw: the very outlier
we want to catch inflates both the mean and the standard deviation, pulling its
own z-score down and hiding it (the "masking" effect). A single large fraudulent
charge can therefore make itself look ordinary.

## Decision
Use a **robust z-score** built on the median and the median absolute deviation
(MAD): `z = 0.6745 * (x - median) / MAD`. The median and MAD are insensitive to a
handful of outliers, so an anomalous amount stands out instead of masking itself.
Accounts with fewer than `min_samples` postings are skipped (not enough history
to judge), and accounts whose amounts are all identical (MAD = 0) produce no
anomalies.

## Scope
The check only runs on **expense and income** accounts, where a single account's
postings are expected to be of a similar size. Asset, liability and equity
accounts — a cash/clearing account above all — aggregate heterogeneous flows
(capital, sales, every payment), so their amounts are legitimately spread out and
flagging them produces noise, not signal.

## Consequences
- Catches outliers that a mean/standard-deviation rule would miss.
- Deterministic and explainable: the flag reports the amount, the account's
  typical (median) amount, and how many robust standard deviations away it is.
- It is a univariate amount check, not fraud detection. It does not model
  seasonality, vendors, or multi-feature patterns; those would need a richer
  model trained on labelled history.
