# ADR 0002 — Make the journal append-only and hash-chained

## Status
Accepted.

## Context
An audit trail is only credible if a historical entry cannot be quietly changed.
A plain list of entries offers no such guarantee: anyone with write access could
edit a past amount and leave no trace.

## Decision
Each posted entry stores `entry_hash = SHA-256(prev_hash + canonical_content)`,
where `canonical_content` is a deterministic JSON serialisation of the entry's
business fields (sequence, date, description, memo, lines). The first entry
chains from a fixed genesis hash. `Ledger.verify()` recomputes the chain and
returns the sequence number of the first entry whose stored hash no longer
matches — the point of tampering.

## Consequences
- Tamper-*evidence*: an edit to any historical entry breaks every hash after it,
  so undetected modification is not possible.
- It is not tamper-*prevention* and not a blockchain: there is no consensus or
  distribution. For a single-writer ledger that is the right amount of mechanism.
- Canonical serialisation must stay stable; changing it would invalidate existing
  chains, so it is kept deliberately minimal and explicit.
