"""
Aggregate investment performance across all brokerage accounts
(Finance Design Rev 3 Section 4.5).
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import get_user_base_currency
from server.app.domains.finance.services.investment_performance._helpers import (
    _list_investment_accounts,
)
from server.app.domains.finance.services.investment_performance.account import (
    compute_account_performance,
)


async def compute_aggregate_performance(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
    period_start: date | None = None,
) -> dict:
    """
    Aggregate performance across every brokerage account owned by the user.
    Returned dict uses account_id=None, account_name=None to indicate the
    portfolio-wide view.
    """
    if as_of_date is None:
        as_of_date = date.today()
    if period_start is None:
        period_start = date(as_of_date.year, 1, 1)

    base_currency = await get_user_base_currency(db, user_id)
    accounts = await _list_investment_accounts(db, user_id)

    total_value = Decimal("0")
    total_cost_basis = Decimal("0")
    total_invested = Decimal("0")
    unrealized_gain = Decimal("0")
    realized_gain = Decimal("0")
    dividend_income = Decimal("0")
    holdings_out: list[dict] = []

    for node, _account_node in accounts:
        result = await compute_account_performance(
            db, user_id, node.id, as_of_date, period_start
        )
        if result is None:
            continue
        total_value += result["total_value"]
        total_cost_basis += result["total_cost_basis"]
        total_invested += result["total_invested"]
        unrealized_gain += result["unrealized_gain"]
        realized_gain += result["realized_gain"]
        dividend_income += result["dividend_income"]
        holdings_out.extend(result["holdings"])

    simple_return: float | None = None
    if total_invested > 0:
        simple_return = float(
            (total_value - total_invested + dividend_income) / total_invested
        )

    explanation = DerivedExplanation(
        summary=(
            f"Aggregate investment performance across {len(accounts)} "
            f"brokerage account(s): value {total_value}, "
            f"unrealized {unrealized_gain}, realized {realized_gain}, "
            f"dividends {dividend_income}."
        ),
        factors=[
            DerivedFactor(
                signal="accounts_considered", value=len(accounts), weight=1.0
            ),
            DerivedFactor(
                signal="total_value", value=str(total_value), weight=1.0
            ),
            DerivedFactor(
                signal="total_invested",
                value=str(total_invested),
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
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "account_id": None,
        "account_name": None,
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
