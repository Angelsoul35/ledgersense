# ADR 0001 — Represent money as integer cents

## Status
Accepted.

## Context
Monetary amounts need exact arithmetic. IEEE-754 floating point cannot represent
most decimal fractions exactly (`0.1 + 0.2 == 0.30000000000000004`), so a ledger
built on floats accumulates rounding error and a trial balance that should net to
zero does not.

## Decision
Every amount in the system is an `int` number of **cents**. Formatting to a
currency string happens only at the presentation edge (CLI/API), never in the
arithmetic.

## Consequences
- Addition and subtraction are exact; a balanced entry is exactly balanced.
- Callers must pass cents (`150000` for `$1,500.00`), which the API documents.
- Sub-cent amounts (some FX, interest) are out of scope; a production system
  would use a scaled integer or `Decimal` with an explicit rounding policy.
