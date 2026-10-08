"""FastAPI surface over the ledger service."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .service import LedgerService

app = FastAPI(title="LedgerSense", version="1.0.0")
_service: LedgerService | None = None


def service() -> LedgerService:
    global _service
    if _service is None:
        _service = LedgerService()
    return _service


class CategorizeRequest(BaseModel):
    description: str = Field(min_length=1)


class ExpenseRequest(BaseModel):
    date: str
    description: str = Field(min_length=1)
    cents: int = Field(gt=0)
    paid_from: str = "1000"


@app.post("/categorize")
def categorize(req: CategorizeRequest) -> dict:
    s = service().categorize(req.description)
    return {
        "account_code": s.account_code,
        "account_name": s.account_name,
        "confidence": round(s.confidence, 4),
        "needs_review": s.needs_review,
        "top_terms": s.top_terms,
    }


@app.post("/expense")
def record_expense(req: ExpenseRequest) -> dict:
    r = service().record_expense(req.date, req.description, req.cents, req.paid_from)
    return {
        "posted": r.posted,
        "note": r.note,
        "account_code": r.suggestion.account_code,
        "account_name": r.suggestion.account_name,
        "confidence": round(r.suggestion.confidence, 4),
        "seq": r.entry.seq if r.entry else None,
    }


@app.get("/trial-balance")
def trial_balance() -> dict:
    rows, total_d, total_c = service().ledger.trial_balance()
    return {
        "balanced": total_d == total_c,
        "total_debits": total_d,
        "total_credits": total_c,
        "rows": [
            {
                "code": r.code,
                "name": r.name,
                "type": r.type.value,
                "debit": r.debit_cents,
                "credit": r.credit_cents,
            }
            for r in rows
        ],
    }


@app.get("/anomalies")
def anomalies() -> dict:
    found = service().anomalies()
    return {
        "count": len(found),
        "anomalies": [
            {
                "seq": a.seq,
                "account_code": a.account_code,
                "amount_cents": a.amount_cents,
                "robust_z": a.robust_z,
                "reason": a.reason,
            }
            for a in found
        ],
    }


@app.get("/verify")
def verify() -> dict:
    ok, broken = service().ledger.verify()
    return {"intact": ok, "first_broken_seq": broken}
