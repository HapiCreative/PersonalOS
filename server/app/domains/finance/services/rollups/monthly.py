"""
Finance Phase F2-C — Monthly rollup (finance_monthly_rollups).

Section 4.8 / F2.3.3. Refreshed nightly.
Tracks net worth deltas, cashflow totals, investment return, and goal
contributions for the calendar month.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.models.rollups import FinanceMonthlyRollup
from server.app.domains.finance.services._helpers import (
    end_of_month,
    start_of_month,
)
from server.app.domains.finance.services.cashflow import compute_cashflow
from server.app.domains.finance.services.investment_performance import (
    _compute_realized_gain,
    _list_investment_accounts,
    _sum_dividends,
)
from server.app.domains.finance.services.net_worth import compute_net_worth
from server.app.domains.finance.services.rollups._helpers import (
    top_expense_categories,
)


async def compute_finance_monthly_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    month_start: date,
) -> FinanceMonthlyRollup:
    """F2.3.3: Upsert a finance_monthly_rollups row."""
    month_start = start_of_month(month_start)
    month_end = end_of_month(month_start)

    cashflow_result = await compute_cashflow(db, user_id, month_start, month_end)
    nw_start = await compute_net_worth(db, user_id, month_start)
    nw_end = await compute_net_worth(db, user_id, month_end)
    top_cats = await top_expense_categories(
        db, user_id, month_start, month_end
    )

    # Investment return = realized gains (period) + dividends (period).
    # Unrealized delta is captured by net_worth_change already.
    investment_return = Decimal("0")
    investment_accounts = await _list_investment_accounts(db, user_id)
    account_ids = [node.id for node, _ in investment_accounts]
    for node, _acct in investment_accounts:
        realized = await _compute_realized_gain(
            db, user_id, node.id, month_start, month_end
        )
        investment_return += realized
    investment_return += await _sum_dividends(
        db, user_id, account_ids, month_start, month_end
    )

    # Goal contributions: F3 review pipeline computes per-goal deltas. Here
    # we record only the totals placeholder — the goal_progress service is
    # authoritative and its cached current_amount is refreshed elsewhere.
    goal_contribs: list[dict] = []

    stmt = select(FinanceMonthlyRollup).where(
        FinanceMonthlyRollup.user_id == user_id,
        FinanceMonthlyRollup.month == month_start,
    )
    rollup = (await db.execute(stmt)).scalar_one_or_none()
    if rollup is None:
        rollup = FinanceMonthlyRollup(user_id=user_id, month=month_start)
        db.add(rollup)

    rollup.net_worth_start = nw_start["net_worth"]
    rollup.net_worth_end = nw_end["net_worth"]
    rollup.net_worth_change = nw_end["net_worth"] - nw_start["net_worth"]
    rollup.total_income = cashflow_result["monthly_income"]
    rollup.total_expenses = cashflow_result["monthly_expenses"]
    rollup.savings_rate = (
        Decimal(str(cashflow_result["savings_rate"]))
        if cashflow_result["savings_rate"] is not None
        else None
    )
    rollup.top_expense_categories = top_cats
    rollup.investment_return = investment_return
    rollup.goal_contributions = goal_contribs
    await db.flush()
    return rollup
