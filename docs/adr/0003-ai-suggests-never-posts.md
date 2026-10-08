# ADR 0003 — The categoriser suggests; it never posts unsupervised

## Status
Accepted.

## Context
A transaction categoriser is useful but fallible. If a misclassification could
write directly to the ledger, a single model error would corrupt the books —
exactly the failure mode that makes accountants distrust "AI bookkeeping".

## Decision
The categoriser returns a `Suggestion` (account, confidence, explanation). The
service auto-posts only when confidence is at or above
`LG_CATEGORISER_MIN_CONFIDENCE`; below it, the charge is returned for a human to
confirm and nothing is posted. All posting goes through `Ledger.post`, which
enforces the balancing and account-existence invariants.

## Consequences
- A misfiring model can mis-*suggest* but can never produce an invalid ledger.
- The confidence threshold is an operator dial: raise it to send more to review,
  lower it to automate more, trading effort against error rate.
- Every suggestion ships with its top contributing terms, so a reviewer can see
  *why* an account was proposed and override it.
