"""Investment performance endpoints (Section 4.5)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.routers.intelligence._helpers import (
    explanation_to_response,
)
from server.app.domains.finance.schemas.derived import (
    InvestmentPerformanceResponse,
)
from server.app.domains.finance.services.investment_performance import (
    compute_account_performance,
    compute_aggregate_performance,
)

router = APIRouter()


def _to_response(result: dict) -> InvestmentPerformanceResponse:
    return InvestmentPerformanceResponse(
        account_id=result["account_id"],
        account_name=result["account_name"],
        as_of_date=result["as_of_date"],
        base_currency=result["base_currency"],
        total_value=result["total_value"],
        total_cost_basis=result["total_cost_basis"],
        total_invested=result["total_invested"],
        unrealized_gain=result["unrealized_gain"],
        realized_gain=result["realized_gain"],
        simple_return=result["simple_return"],
        dividend_income=result["dividend_income"],
        holdings=result["holdings"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/investments", response_model=InvestmentPerformanceResponse)
async def get_aggregate_investment_performance(
    as_of_date: date | None = Query(default=None),
    period_start: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.5: Aggregate performance across all brokerage accounts."""
    result = await compute_aggregate_performance(
        db, user.id, as_of_date, period_start
    )
    return _to_response(result)


@router.get(
    "/investments/{account_id}",
    response_model=InvestmentPerformanceResponse,
)
async def get_account_investment_performance(
    account_id: uuid.UUID,
    as_of_date: date | None = Query(default=None),
    period_start: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.5: Per-brokerage-account performance."""
    result = await compute_account_performance(
        db, user.id, account_id, as_of_date, period_start
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Brokerage account {account_id} not found or not owned by user"
            ),
        )
    return _to_response(result)
