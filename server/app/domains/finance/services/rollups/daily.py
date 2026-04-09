"""
Finance Phase F2-C — Daily rollup (finance_daily_rollups).

Section 4.8 / F2.3.1. Event-driven: refreshed on transaction insert/update/void.
Invariant D-02: fully recomputable.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.models.rollups import FinanceDailyRollup
from server.app.domains.finance.services.cashflow import compute_cashflow
from server.app.domains.finance.services.investment_performance import (
    _get_latest_holdings,
    _get_latest_price,
    _list_investment_accounts,
)
from server.app.domains.finance.services.net_worth import compute_net_worth


async def compute_finance_daily_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
) -> FinanceDailyRollup:
    """
    F2.3.1: Upsert a finance_daily_rollups row for the given date.
    Event-driven: called after transaction create/update/void.
    """
    net_worth_result = await compute_net_worth(db, user_id, target_date)
    cashflow_result = await compute_cashflow(
        db, user_id, target_date, target_date
    )

    # Investment value at target_date (sum of holdings × last known price).
    investment_value = Decimal("0")
    accounts = await _list_investment_accounts(db, user_id)
    for node, _acct in accounts:
        holdings = await _get_latest_holdings(db, user_id, node.id, target_date)
        for h in holdings:
            price_row = await _get_latest_price(db, h.symbol, target_date)
            if price_row is None:
                continue
            investment_value += Decimal(str(h.quantity)) * Decimal(
                str(price_row.price)
            )

    stmt = select(FinanceDailyRollup).where(
        FinanceDailyRollup.user_id == user_id,
        FinanceDailyRollup.date == target_date,
    )
    rollup = (await db.execute(stmt)).scalar_one_or_none()
    if rollup is None:
        rollup = FinanceDailyRollup(user_id=user_id, date=target_date)
        db.add(rollup)

    rollup.net_worth = net_worth_result["net_worth"]
    rollup.liquid_net_worth = net_worth_result["liquid_net_worth"]
    rollup.total_assets = net_worth_result["total_assets"]
    rollup.total_liabilities = net_worth_result["total_liabilities"]
    rollup.daily_income = cashflow_result["monthly_income"]
    rollup.daily_expenses = cashflow_result["monthly_expenses"]
    rollup.daily_net_cashflow = cashflow_result["net_cashflow"]
    rollup.investment_value = investment_value
    await db.flush()
    return rollup


async def refresh_daily_rollup_for_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    affected_date: date,
) -> None:
    """
    Post-mutation hook. Called from the transaction service after
    create/update/void. Best-effort: swallows errors so a rollup-refresh
    failure never aborts the transaction mutation itself.

    Invariant D-02: Derived outputs are recomputable; a failed refresh can be
    repaired by a later event or the nightly backfill job.
    """
    try:
        await compute_finance_daily_rollup(db, user_id, affected_date)
    except Exception:
        pass
