"""
Internal helpers for investment performance computation.

Queries against holdings, market prices, investment transactions, and
dividend transactions. Used by the account + aggregate services and by
rollup sub-modules (daily, monthly, portfolio).
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    AccountType,
    FinancialTransactionStatus,
    FinancialTransactionType,
    InvestmentTransactionType,
    NodeType,
)
from server.app.core.models.node import AccountNode, FinancialTransaction, Node
from server.app.domains.finance.models.investments import (
    InvestmentHolding,
    InvestmentTransaction,
    MarketPrice,
)
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
)


async def _get_latest_holdings(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    as_of_date: date,
) -> list[InvestmentHolding]:
    """
    Return the most recent holding snapshot per symbol for the account,
    filtered to snapshots on or before `as_of_date`.
    """
    subq = (
        select(
            InvestmentHolding.symbol,
            func.max(InvestmentHolding.as_of_date).label("latest"),
        )
        .where(
            InvestmentHolding.user_id == user_id,
            InvestmentHolding.account_id == account_id,
            InvestmentHolding.as_of_date <= as_of_date,
        )
        .group_by(InvestmentHolding.symbol)
        .subquery()
    )
    stmt = (
        select(InvestmentHolding)
        .join(
            subq,
            and_(
                InvestmentHolding.symbol == subq.c.symbol,
                InvestmentHolding.as_of_date == subq.c.latest,
            ),
        )
        .where(
            InvestmentHolding.user_id == user_id,
            InvestmentHolding.account_id == account_id,
        )
    )
    return list((await db.execute(stmt)).scalars().all())


async def _get_latest_price(
    db: AsyncSession, symbol: str, as_of_date: date
) -> MarketPrice | None:
    stmt = (
        select(MarketPrice)
        .where(
            MarketPrice.symbol == symbol,
            MarketPrice.price_date <= as_of_date,
        )
        .order_by(MarketPrice.price_date.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _list_investment_accounts(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[Node, AccountNode]]:
    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(
            Node.owner_id == user_id,
            Node.type == NodeType.ACCOUNT,
            Node.archived_at.is_(None),
            AccountNode.account_type == AccountType.BROKERAGE,
        )
    )
    return list((await db.execute(stmt)).all())


async def _sum_dividends(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_ids: list[uuid.UUID],
    period_start: date,
    period_end: date,
) -> Decimal:
    if not account_ids:
        return Decimal("0")
    stmt = (
        select(
            func.coalesce(
                func.sum(FinancialTransaction.signed_amount), Decimal("0")
            )
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.account_id.in_(account_ids),
            FinancialTransaction.transaction_type == FinancialTransactionType.DIVIDEND,
            FinancialTransaction.status.in_([
                FinancialTransactionStatus.POSTED,
                FinancialTransactionStatus.SETTLED,
            ]),
            FinancialTransaction.occurred_at >= datetime_at_start_of_day(period_start),
            FinancialTransaction.occurred_at <= datetime_at_end_of_day(period_end),
        )
    )
    return Decimal(str((await db.execute(stmt)).scalar_one()))


async def _compute_account_invested(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    as_of_date: date,
) -> Decimal:
    """
    Total invested = SUM(buy) − SUM(sell). Used for simple_return denominator.
    """
    stmt = (
        select(
            InvestmentTransaction.transaction_type,
            func.coalesce(
                func.sum(InvestmentTransaction.total_amount), Decimal("0")
            ),
        )
        .where(
            InvestmentTransaction.user_id == user_id,
            InvestmentTransaction.account_id == account_id,
            InvestmentTransaction.occurred_at <= datetime_at_end_of_day(as_of_date),
        )
        .group_by(InvestmentTransaction.transaction_type)
    )
    rows = (await db.execute(stmt)).all()
    totals: dict[str, Decimal] = {
        str(row[0].value): Decimal(str(row[1])) for row in rows
    }
    invested = totals.get(InvestmentTransactionType.BUY.value, Decimal("0"))
    invested -= totals.get(InvestmentTransactionType.SELL.value, Decimal("0"))
    return invested


async def _compute_realized_gain(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    period_start: date | None,
    period_end: date,
) -> Decimal:
    """
    Realized gain = SUM over sells of (sell_proceeds - avg_cost_basis × qty).
    Average cost basis = total_buy_amount / total_buy_quantity up to sell date.
    Lot tracking deferred to F4.
    """
    stmt = (
        select(InvestmentTransaction)
        .where(
            InvestmentTransaction.user_id == user_id,
            InvestmentTransaction.account_id == account_id,
            InvestmentTransaction.occurred_at <= datetime_at_end_of_day(period_end),
        )
        .order_by(InvestmentTransaction.occurred_at.asc())
    )
    txs = list((await db.execute(stmt)).scalars().all())

    running: dict[str, tuple[Decimal, Decimal]] = {}
    realized = Decimal("0")
    period_start_dt = (
        datetime_at_start_of_day(period_start) if period_start is not None else None
    )

    for tx in txs:
        qty = Decimal(str(tx.quantity))
        total = Decimal(str(tx.total_amount))
        current_qty, current_cost = running.get(
            tx.symbol, (Decimal("0"), Decimal("0"))
        )
        if tx.transaction_type == InvestmentTransactionType.BUY:
            running[tx.symbol] = (current_qty + qty, current_cost + total)
        elif tx.transaction_type == InvestmentTransactionType.SELL:
            if current_qty <= 0:
                continue
            avg_cost = current_cost / current_qty
            cost_of_sold = avg_cost * qty
            gain = total - cost_of_sold
            new_qty = current_qty - qty
            new_cost = current_cost - cost_of_sold
            running[tx.symbol] = (new_qty, new_cost)
            if period_start_dt is None or tx.occurred_at >= period_start_dt:
                realized += gain
    return realized
