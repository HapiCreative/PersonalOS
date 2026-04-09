"""
Finance Phase F2-C — Portfolio rollup (portfolio_rollups).

Section 4.8 / F2.3.4. Refreshed nightly.

Per-account investment rollups with market_movement separated from cash
movement: market_movement = total_value_delta - deposits + withdrawals.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    AccountType,
    FinancialTransactionStatus,
    FinancialTransactionType,
    PortfolioRollupPeriodType,
)
from server.app.core.models.node import AccountNode, FinancialTransaction, Node
from server.app.domains.finance.models.rollups import PortfolioRollup
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
    start_of_month,
)
from server.app.domains.finance.services.investment_performance import (
    _compute_realized_gain,
    _get_latest_holdings,
    _get_latest_price,
    _sum_dividends,
)


POSTED = [
    FinancialTransactionStatus.POSTED,
    FinancialTransactionStatus.SETTLED,
]


async def _cash_movement(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    period_start: date,
    period_end: date,
    direction: FinancialTransactionType,
) -> Decimal:
    """Sum transfer_in (deposits) or transfer_out (withdrawals) in period."""
    col = (
        FinancialTransaction.signed_amount
        if direction == FinancialTransactionType.TRANSFER_IN
        else func.abs(FinancialTransaction.signed_amount)
    )
    stmt = (
        select(func.coalesce(func.sum(col), Decimal("0")))
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.account_id == account_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type == direction,
            FinancialTransaction.status.in_(POSTED),
            FinancialTransaction.occurred_at >= datetime_at_start_of_day(period_start),
            FinancialTransaction.occurred_at <= datetime_at_end_of_day(period_end),
        )
    )
    return Decimal(str((await db.execute(stmt)).scalar_one()))


async def compute_portfolio_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    period_date: date,
    period_type: PortfolioRollupPeriodType = PortfolioRollupPeriodType.DAILY,
) -> PortfolioRollup | None:
    """
    F2.3.4: Upsert a portfolio_rollups row for a single brokerage account.
    Returns None if the account is missing or not brokerage.
    """
    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(
            Node.id == account_id,
            Node.owner_id == user_id,
            AccountNode.account_type == AccountType.BROKERAGE,
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None

    if period_type == PortfolioRollupPeriodType.DAILY:
        period_start = period_date
    else:
        period_start = start_of_month(period_date)
    period_end = period_date

    holdings = await _get_latest_holdings(db, user_id, account_id, period_end)
    total_value = Decimal("0")
    total_cost_basis = Decimal("0")
    top_holding: dict | None = None
    top_value = Decimal("0")
    for h in holdings:
        quantity = Decimal(str(h.quantity))
        cost_basis = Decimal(str(h.cost_basis or Decimal("0")))
        price_row = await _get_latest_price(db, h.symbol, period_end)
        current_price = Decimal(str(price_row.price)) if price_row else None
        value = quantity * current_price if current_price is not None else Decimal("0")
        total_value += value
        total_cost_basis += cost_basis
        if value > top_value:
            top_value = value
            top_holding = {
                "symbol": h.symbol,
                "value": str(value),
                "asset_type": h.asset_type.value,
            }
    unrealized_gain = total_value - total_cost_basis

    realized_gain_period = await _compute_realized_gain(
        db, user_id, account_id, period_start, period_end
    )
    dividend_income_period = await _sum_dividends(
        db, user_id, [account_id], period_start, period_end
    )
    deposits_period = await _cash_movement(
        db, user_id, account_id, period_start, period_end,
        FinancialTransactionType.TRANSFER_IN,
    )
    withdrawals_period = await _cash_movement(
        db, user_id, account_id, period_start, period_end,
        FinancialTransactionType.TRANSFER_OUT,
    )

    # Prior rollup provides the earlier total_value anchor for market_movement.
    prev_stmt = (
        select(PortfolioRollup)
        .where(
            PortfolioRollup.user_id == user_id,
            PortfolioRollup.account_id == account_id,
            PortfolioRollup.period_type == period_type,
            PortfolioRollup.period_date < period_end,
        )
        .order_by(PortfolioRollup.period_date.desc())
        .limit(1)
    )
    prev_rollup = (await db.execute(prev_stmt)).scalar_one_or_none()
    prior_value = (
        Decimal(str(prev_rollup.total_value))
        if prev_rollup is not None and prev_rollup.total_value is not None
        else Decimal("0")
    )
    market_movement = (
        (total_value - prior_value) - deposits_period + withdrawals_period
    )

    stmt = select(PortfolioRollup).where(
        PortfolioRollup.user_id == user_id,
        PortfolioRollup.account_id == account_id,
        PortfolioRollup.period_date == period_end,
        PortfolioRollup.period_type == period_type,
    )
    rollup = (await db.execute(stmt)).scalar_one_or_none()
    if rollup is None:
        rollup = PortfolioRollup(
            user_id=user_id,
            account_id=account_id,
            period_date=period_end,
            period_type=period_type,
        )
        db.add(rollup)

    rollup.total_value = total_value
    rollup.total_cost_basis = total_cost_basis
    rollup.unrealized_gain = unrealized_gain
    rollup.realized_gain_period = realized_gain_period
    rollup.dividend_income_period = dividend_income_period
    rollup.deposits_period = deposits_period
    rollup.withdrawals_period = withdrawals_period
    rollup.market_movement = market_movement
    rollup.concentration_top_holding = top_holding
    await db.flush()
    return rollup
