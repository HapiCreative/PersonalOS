"""Cashflow analytics endpoint (Section 4.2)."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.routers.intelligence._helpers import (
    explanation_to_response,
)
from server.app.domains.finance.schemas.derived import CashflowResponse
from server.app.domains.finance.services._helpers import (
    end_of_month,
    start_of_month,
)
from server.app.domains.finance.services.cashflow import compute_cashflow

router = APIRouter()


@router.get("/cashflow", response_model=CashflowResponse)
async def get_cashflow(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Section 4.2: Cashflow analytics.
    Invariant F-07: transfer + investment transaction types excluded.
    Defaults to the current calendar month.
    """
    today = date.today()
    if period_start is None:
        period_start = start_of_month(today)
    if period_end is None:
        period_end = end_of_month(today)
    result = await compute_cashflow(db, user.id, period_start, period_end)
    return CashflowResponse(
        period_start=result["period_start"],
        period_end=result["period_end"],
        days_in_period=result["days_in_period"],
        monthly_income=result["monthly_income"],
        monthly_expenses=result["monthly_expenses"],
        net_cashflow=result["net_cashflow"],
        savings_rate=result["savings_rate"],
        burn_rate=result["burn_rate"],
        pending_income=result["pending_income"],
        pending_expenses=result["pending_expenses"],
        transaction_count=result["transaction_count"],
        explanation=explanation_to_response(result["explanation"]),
    )
