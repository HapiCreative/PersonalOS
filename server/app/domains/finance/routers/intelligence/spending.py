"""Spending intelligence endpoints (Section 4.3)."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.routers.intelligence._helpers import (
    explanation_to_response,
)
from server.app.domains.finance.schemas.derived import (
    CategoryBreakdownResponse,
    LeakageCandidatesResponse,
    MerchantConcentrationResponse,
    SpendCreepResponse,
    SpendingAnomaly,
    SpendingAnomalyResponse,
    SpendingTrendResponse,
)
from server.app.domains.finance.services._helpers import (
    end_of_month,
    start_of_month,
)
from server.app.domains.finance.services.spending import (
    compute_category_breakdown,
    compute_leakage_candidates,
    compute_merchant_concentration,
    compute_spend_creep,
    compute_spending_anomalies,
    compute_spending_trends,
)

router = APIRouter()


def _default_period(period_start: date | None, period_end: date | None) -> tuple[date, date]:
    today = date.today()
    if period_start is None:
        period_start = start_of_month(today)
    if period_end is None:
        period_end = end_of_month(today)
    return period_start, period_end


@router.get("/spending/categories", response_model=CategoryBreakdownResponse)
async def get_category_breakdown(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Category breakdown with hierarchy rollup."""
    period_start, period_end = _default_period(period_start, period_end)
    result = await compute_category_breakdown(
        db, user.id, period_start, period_end
    )
    return CategoryBreakdownResponse(
        period_start=result["period_start"],
        period_end=result["period_end"],
        total_spend=result["total_spend"],
        categories=result["categories"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/spending/trends", response_model=SpendingTrendResponse)
async def get_spending_trends(
    as_of_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Trend detection — 1.5× rolling 3-month average."""
    result = await compute_spending_trends(db, user.id, as_of_date)
    return SpendingTrendResponse(
        as_of_date=result["as_of_date"],
        trending_categories=result["trending_categories"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/spending/anomalies", response_model=SpendingAnomalyResponse)
async def get_spending_anomalies(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    lookback_days: int = Query(default=180, ge=30, le=720),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Anomaly detection — 3× category median."""
    period_start, period_end = _default_period(period_start, period_end)
    result = await compute_spending_anomalies(
        db, user.id, period_start, period_end, lookback_days
    )
    return SpendingAnomalyResponse(
        period_start=result["period_start"],
        period_end=result["period_end"],
        anomalies=[
            SpendingAnomaly(
                transaction_id=a["transaction_id"],
                account_id=a["account_id"],
                category_id=a["category_id"],
                category_name=a["category_name"],
                amount=a["amount"],
                currency=a["currency"],
                occurred_at=a["occurred_at"],
                category_median=a["category_median"],
                ratio=a["ratio"],
                counterparty=a["counterparty"],
                explanation=explanation_to_response(a["explanation"]),
            )
            for a in result["anomalies"]
        ],
    )


@router.get(
    "/spending/merchant-concentration",
    response_model=MerchantConcentrationResponse,
)
async def get_merchant_concentration(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    threshold: float = Query(default=0.30, ge=0.0, le=1.0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Merchant concentration — pre-F3 fuzzy match."""
    period_start, period_end = _default_period(period_start, period_end)
    result = await compute_merchant_concentration(
        db, user.id, period_start, period_end, threshold
    )
    return MerchantConcentrationResponse(
        period_start=result["period_start"],
        period_end=result["period_end"],
        threshold=result["threshold"],
        concentrated_merchants=result["concentrated_merchants"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/spending/spend-creep", response_model=SpendCreepResponse)
async def get_spend_creep(
    as_of_date: date | None = Query(default=None),
    min_delta_pct: float = Query(default=0.10, ge=0.0, le=2.0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Spend creep — consecutive rolling 3-month windows."""
    result = await compute_spend_creep(db, user.id, as_of_date, min_delta_pct)
    return SpendCreepResponse(
        as_of_date=result["as_of_date"],
        creeping_categories=result["creeping_categories"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/spending/leakage", response_model=LeakageCandidatesResponse)
async def get_leakage_candidates(
    period_start: date | None = Query(default=None),
    period_end: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.3: Leakage candidates — pre-F3 frequency heuristic."""
    today = date.today()
    if period_start is None:
        period_start = today - timedelta(days=90)
    if period_end is None:
        period_end = today
    result = await compute_leakage_candidates(
        db, user.id, period_start, period_end
    )
    return LeakageCandidatesResponse(
        period_start=result["period_start"],
        period_end=result["period_end"],
        candidates=result["candidates"],
        explanation=explanation_to_response(result["explanation"]),
    )
