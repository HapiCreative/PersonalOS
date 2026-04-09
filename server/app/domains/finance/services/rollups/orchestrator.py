"""
Finance Phase F2-C — Rollup orchestration (nightly job + backfill).

Section 4.8 / F2.3. Coordinates weekly, monthly, and portfolio rollups on a
nightly schedule, and provides backfill utilities for daily rollups.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import PortfolioRollupPeriodType
from server.app.domains.finance.services._helpers import (
    day_range,
    end_of_month,
)
from server.app.domains.finance.services.goal_progress import (
    refresh_all_goal_progress,
)
from server.app.domains.finance.services.investment_performance import (
    _list_investment_accounts,
)
from server.app.domains.finance.services.rollups.daily import (
    compute_finance_daily_rollup,
)
from server.app.domains.finance.services.rollups.monthly import (
    compute_finance_monthly_rollup,
)
from server.app.domains.finance.services.rollups.portfolio import (
    compute_portfolio_rollup,
)
from server.app.domains.finance.services.rollups.weekly import (
    compute_finance_weekly_rollup,
)


async def refresh_nightly_rollups(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
) -> dict:
    """
    Nightly scheduled job: refresh weekly + monthly + portfolio rollups and
    the cached goal progress for one user.

    Daily rollups are event-driven during the day; the nightly job refreshes
    today's daily rollup as a safety net and leaves historical backfill to
    `backfill_daily_rollups`.

    Invariant D-02: every output is recomputable, so this job is idempotent
    and safe to re-run at any time.
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Safety-net daily rollup refresh for today.
    await compute_finance_daily_rollup(db, user_id, as_of_date)

    week_rollup = await compute_finance_weekly_rollup(db, user_id, as_of_date)
    month_rollup = await compute_finance_monthly_rollup(db, user_id, as_of_date)

    portfolio_count = 0
    accounts = await _list_investment_accounts(db, user_id)
    for node, _acct in accounts:
        daily = await compute_portfolio_rollup(
            db, user_id, node.id, as_of_date, PortfolioRollupPeriodType.DAILY
        )
        if daily is not None:
            portfolio_count += 1
        monthly = await compute_portfolio_rollup(
            db,
            user_id,
            node.id,
            end_of_month(as_of_date),
            PortfolioRollupPeriodType.MONTHLY,
        )
        if monthly is not None:
            portfolio_count += 1

    # Invariant S-01: refresh cached goal progress.
    goal_updates = await refresh_all_goal_progress(db, user_id, as_of_date)

    return {
        "daily_count": 1,
        "weekly_count": 1 if week_rollup is not None else 0,
        "monthly_count": 1 if month_rollup is not None else 0,
        "portfolio_count": portfolio_count,
        "goal_progress_updated": goal_updates,
        "start_date": as_of_date,
        "end_date": as_of_date,
    }


async def backfill_daily_rollups(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> int:
    """
    Backfill finance_daily_rollups across a date range. Used for recovery
    after a schema change, missed events, or fresh imports.
    """
    count = 0
    for d in day_range(start_date, end_date):
        await compute_finance_daily_rollup(db, user_id, d)
        count += 1
    return count
