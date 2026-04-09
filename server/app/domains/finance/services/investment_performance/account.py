"""
Per-account investment performance (Finance Design Rev 3 Section 4.5).

Invariants:
- F-07: investment transaction types feed this service, not cashflow.
- D-01: DerivedExplanation required on every output.
- D-02: every output is recomputable from Core + Temporal data.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import AccountType, NodeType
from server.app.core.models.node import AccountNode, Node
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services.investment_performance._helpers import (
    _compute_account_invested,
    _compute_realized_gain,
    _get_latest_holdings,
    _get_latest_price,
    _sum_dividends,
)


async def compute_account_performance(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    as_of_date: date | None = None,
    period_start: date | None = None,
) -> dict | None:
    """
    Section 4.5: Compute investment performance for a single brokerage account.
    Returns None if the account is missing, not brokerage, or not owned by user.
    """
    if as_of_date is None:
        as_of_date = date.today()
    if period_start is None:
        period_start = date(as_of_date.year, 1, 1)  # Year-to-date default

    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(
            Node.id == account_id,
            Node.owner_id == user_id,
            Node.type == NodeType.ACCOUNT,
            AccountNode.account_type == AccountType.BROKERAGE,
        )
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    node, account_node = row

    holdings = await _get_latest_holdings(db, user_id, account_id, as_of_date)

    total_value = Decimal("0")
    total_cost_basis = Decimal("0")
    holdings_out: list[dict] = []
    for h in holdings:
        quantity = Decimal(str(h.quantity))
        cost_basis = Decimal(str(h.cost_basis or Decimal("0")))
        price_row = await _get_latest_price(db, h.symbol, as_of_date)
        current_price = Decimal(str(price_row.price)) if price_row else None
        current_value = (
            quantity * current_price if current_price is not None else None
        )
        if current_value is not None:
            total_value += current_value
        unrealized = (
            current_value - cost_basis if current_value is not None else None
        )
        total_cost_basis += cost_basis
        holdings_out.append({
            "symbol": h.symbol,
            "quantity": quantity,
            "cost_basis": cost_basis,
            "current_price": current_price,
            "total_value": current_value,
            "unrealized_gain": unrealized,
            "asset_type": h.asset_type.value,
            "currency": h.currency,
        })

    unrealized_gain = total_value - total_cost_basis
    total_invested = await _compute_account_invested(
        db, user_id, account_id, as_of_date
    )
    dividend_income = await _sum_dividends(
        db, user_id, [account_id], period_start, as_of_date
    )
    realized_gain = await _compute_realized_gain(
        db, user_id, account_id, period_start, as_of_date
    )

    simple_return: float | None = None
    if total_invested > 0:
        simple_return = float(
            (total_value - total_invested + dividend_income) / total_invested
        )

    base_currency = account_node.currency

    explanation = DerivedExplanation(
        summary=(
            f"Investment performance for '{node.title}' as of {as_of_date}: "
            f"value {total_value}, cost basis {total_cost_basis}, "
            f"unrealized {unrealized_gain}, realized (period) {realized_gain}, "
            f"dividends {dividend_income}."
        ),
        factors=[
            DerivedFactor(signal="total_value", value=str(total_value), weight=1.0),
            DerivedFactor(
                signal="total_cost_basis",
                value=str(total_cost_basis),
                weight=1.0,
            ),
            DerivedFactor(
                signal="unrealized_gain",
                value=str(unrealized_gain),
                weight=1.0,
            ),
            DerivedFactor(
                signal="realized_gain",
                value=str(realized_gain),
                weight=1.0,
            ),
            DerivedFactor(
                signal="dividend_income",
                value=str(dividend_income),
                weight=0.8,
            ),
            DerivedFactor(
                signal="cost_basis_method",
                value="average (lot tracking deferred to F4)",
                weight=0.6,
            ),
            DerivedFactor(
                signal="holdings_count", value=len(holdings_out), weight=1.0
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "account_id": account_id,
        "account_name": node.title,
        "as_of_date": as_of_date,
        "base_currency": base_currency,
        "total_value": total_value,
        "total_cost_basis": total_cost_basis,
        "total_invested": total_invested,
        "unrealized_gain": unrealized_gain,
        "realized_gain": realized_gain,
        "simple_return": simple_return,
        "dividend_income": dividend_income,
        "holdings": holdings_out,
        "explanation": explanation,
    }
