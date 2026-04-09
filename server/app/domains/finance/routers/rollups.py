"""
Finance Phase F2-C — Rollup admin + retrieval endpoints.

Exposes finance_daily_rollups, finance_weekly_rollups, finance_monthly_rollups,
portfolio_rollups tables plus a manual nightly refresh trigger.

Invariant D-02: rollups are recomputable. Invariant D-03: non-canonical.
"""

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.enums import PortfolioRollupPeriodType
from server.app.core.models.user import User
from server.app.domains.finance.models.rollups import (
    FinanceDailyRollup,
    FinanceMonthlyRollup,
    FinanceWeeklyRollup,
    PortfolioRollup,
)
from server.app.domains.finance.schemas.derived import (
    FinanceDailyRollupResponse,
    FinanceMonthlyRollupResponse,
    FinanceWeeklyRollupResponse,
    PortfolioRollupResponse,
    RollupRefreshResponse,
)
from server.app.domains.finance.services.rollups import (
    backfill_daily_rollups,
    refresh_nightly_rollups,
)

router = APIRouter(prefix="/rollups", tags=["finance-rollups"])


@router.get("/daily", response_model=list[FinanceDailyRollupResponse])
async def list_daily_rollups(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F2.3.1: Finance daily rollups in a date range."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    stmt = (
        select(FinanceDailyRollup)
        .where(
            FinanceDailyRollup.user_id == user.id,
            FinanceDailyRollup.date >= start_date,
            FinanceDailyRollup.date <= end_date,
        )
        .order_by(FinanceDailyRollup.date.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [FinanceDailyRollupResponse.model_validate(r) for r in rows]


@router.get("/weekly", response_model=list[FinanceWeeklyRollupResponse])
async def list_weekly_rollups(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F2.3.2: Finance weekly rollups in a date range."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(weeks=12)
    stmt = (
        select(FinanceWeeklyRollup)
        .where(
            FinanceWeeklyRollup.user_id == user.id,
            FinanceWeeklyRollup.week_start_date >= start_date,
            FinanceWeeklyRollup.week_start_date <= end_date,
        )
        .order_by(FinanceWeeklyRollup.week_start_date.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [FinanceWeeklyRollupResponse.model_validate(r) for r in rows]


@router.get("/monthly", response_model=list[FinanceMonthlyRollupResponse])
async def list_monthly_rollups(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F2.3.3: Finance monthly rollups in a date range."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = date(end_date.year - 1, end_date.month, 1)
    stmt = (
        select(FinanceMonthlyRollup)
        .where(
            FinanceMonthlyRollup.user_id == user.id,
            FinanceMonthlyRollup.month >= start_date,
            FinanceMonthlyRollup.month <= end_date,
        )
        .order_by(FinanceMonthlyRollup.month.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [FinanceMonthlyRollupResponse.model_validate(r) for r in rows]


@router.get("/portfolio", response_model=list[PortfolioRollupResponse])
async def list_portfolio_rollups(
    account_id: uuid.UUID | None = Query(default=None),
    period_type: PortfolioRollupPeriodType = Query(
        default=PortfolioRollupPeriodType.DAILY
    ),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F2.3.4: Portfolio rollups, optionally filtered by account."""
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=90)
    filters = [
        PortfolioRollup.user_id == user.id,
        PortfolioRollup.period_type == period_type,
        PortfolioRollup.period_date >= start_date,
        PortfolioRollup.period_date <= end_date,
    ]
    if account_id is not None:
        filters.append(PortfolioRollup.account_id == account_id)
    stmt = (
        select(PortfolioRollup)
        .where(and_(*filters))
        .order_by(PortfolioRollup.period_date.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [PortfolioRollupResponse.model_validate(r) for r in rows]


@router.post("/refresh", response_model=RollupRefreshResponse)
async def trigger_nightly_refresh(
    as_of_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger the nightly rollup refresh. In production this runs as
    a scheduled background job; this endpoint lets the user/admin force a run.
    Invariant D-02: idempotent — safe to re-run at any time.
    """
    result = await refresh_nightly_rollups(db, user.id, as_of_date)
    return RollupRefreshResponse(**result)


@router.post("/backfill-daily", response_model=RollupRefreshResponse)
async def trigger_daily_backfill(
    start_date: date,
    end_date: date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Backfill finance_daily_rollups across a date range."""
    count = await backfill_daily_rollups(db, user.id, start_date, end_date)
    return RollupRefreshResponse(
        daily_count=count,
        weekly_count=0,
        monthly_count=0,
        portfolio_count=0,
        goal_progress_updated=0,
        start_date=start_date,
        end_date=end_date,
    )
