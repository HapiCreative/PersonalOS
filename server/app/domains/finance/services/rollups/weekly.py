"""
Finance Phase F2-C — Weekly rollup (finance_weekly_rollups).

Section 4.8 / F2.3.2. Refreshed nightly.
Includes top_expense_categories and category_variance_flags as JSONB blobs
for Weekly Review consumption.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.models.rollups import FinanceWeeklyRollup
from server.app.domains.finance.services._helpers import (
    end_of_week,
    start_of_week,
)
from server.app.domains.finance.services.cashflow import compute_cashflow
from server.app.domains.finance.services.net_worth import compute_net_worth
from server.app.domains.finance.services.rollups._helpers import (
    top_expense_categories,
    variance_flags_vs_prior_4_weeks,
)


async def compute_finance_weekly_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start: date,
) -> FinanceWeeklyRollup:
    """F2.3.2: Upsert a finance_weekly_rollups row."""
    week_start = start_of_week(week_start)
    week_end = end_of_week(week_start)

    cashflow_result = await compute_cashflow(db, user_id, week_start, week_end)
    nw_start = await compute_net_worth(db, user_id, week_start)
    nw_end = await compute_net_worth(db, user_id, week_end)

    top_cats = await top_expense_categories(db, user_id, week_start, week_end)
    variance_flags = await variance_flags_vs_prior_4_weeks(
        db, user_id, week_start, week_end
    )

    stmt = select(FinanceWeeklyRollup).where(
        FinanceWeeklyRollup.user_id == user_id,
        FinanceWeeklyRollup.week_start_date == week_start,
    )
    rollup = (await db.execute(stmt)).scalar_one_or_none()
    if rollup is None:
        rollup = FinanceWeeklyRollup(
            user_id=user_id,
            week_start_date=week_start,
            week_end_date=week_end,
        )
        db.add(rollup)

    rollup.week_end_date = week_end
    rollup.total_income = cashflow_result["monthly_income"]
    rollup.total_expenses = cashflow_result["monthly_expenses"]
    rollup.net_cashflow = cashflow_result["net_cashflow"]
    rollup.savings_rate = (
        Decimal(str(cashflow_result["savings_rate"]))
        if cashflow_result["savings_rate"] is not None
        else None
    )
    rollup.top_expense_categories = top_cats
    rollup.category_variance_flags = variance_flags
    rollup.net_worth_start = nw_start["net_worth"]
    rollup.net_worth_end = nw_end["net_worth"]
    rollup.net_worth_delta = nw_end["net_worth"] - nw_start["net_worth"]
    await db.flush()
    return rollup
