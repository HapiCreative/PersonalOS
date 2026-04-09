"""
Finance Phase F2-C — Cashflow Analytics (Derived layer).

Ref: Finance Design Rev 3 Section 4.2.

Metrics:
- monthly_income  = SUM(signed_amount) WHERE type IN (income, dividend, interest, refund)
                    AND status IN (posted, settled)
- monthly_expenses = SUM(ABS(signed_amount)) WHERE type IN (expense, fee)
                     AND status IN (posted, settled)
- net_cashflow    = monthly_income - monthly_expenses
- savings_rate    = net_cashflow / monthly_income
- burn_rate       = monthly_expenses / 30 (daily average)

Invariant F-07: transfer + investment transaction types are EXCLUDED.
Invariant D-01: every output includes a DerivedExplanation.
Invariant D-02: every output is recomputable from Core + Temporal data.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    FinancialTransactionStatus,
    FinancialTransactionType,
)
from server.app.core.models.node import FinancialTransaction
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
)


# Invariant F-07: income-side types included in cashflow
INCOME_TYPES: set[FinancialTransactionType] = {
    FinancialTransactionType.INCOME,
    FinancialTransactionType.DIVIDEND,
    FinancialTransactionType.INTEREST,
    FinancialTransactionType.REFUND,
}

# Invariant F-07: expense-side types included in cashflow
EXPENSE_TYPES: set[FinancialTransactionType] = {
    FinancialTransactionType.EXPENSE,
    FinancialTransactionType.FEE,
}

# Invariant F-07: types EXCLUDED from cashflow (transfer + investment)
CASHFLOW_EXCLUDED_TYPES: set[FinancialTransactionType] = {
    FinancialTransactionType.TRANSFER_IN,
    FinancialTransactionType.TRANSFER_OUT,
    FinancialTransactionType.INVESTMENT_BUY,
    FinancialTransactionType.INVESTMENT_SELL,
    FinancialTransactionType.ADJUSTMENT,
}


async def compute_cashflow(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> dict:
    """
    Section 4.2: Compute cashflow metrics for an arbitrary period.

    `monthly_income` / `monthly_expenses` are named per the spec but accept
    any period length; burn_rate still normalizes to a per-day figure by
    dividing total_expenses by 30 as specified in the design doc.
    """
    start_dt = datetime_at_start_of_day(period_start)
    end_dt = datetime_at_end_of_day(period_end)

    posted_statuses = [
        FinancialTransactionStatus.POSTED,
        FinancialTransactionStatus.SETTLED,
    ]

    # Invariant F-07: filter strictly to cashflow-eligible types.
    # Income: SUM(signed_amount) — signed_amount is already positive for
    # income, dividend, interest, refund by the generated column (F-02).
    income_stmt = (
        select(
            func.coalesce(
                func.sum(FinancialTransaction.signed_amount), Decimal("0")
            ),
            func.count(),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(list(INCOME_TYPES)),
            FinancialTransaction.status.in_(posted_statuses),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    income_row = (await db.execute(income_stmt)).one()
    monthly_income: Decimal = Decimal(str(income_row[0]))
    income_count: int = income_row[1] or 0

    # Expenses: SUM(ABS(signed_amount)) — use absolute value since
    # signed_amount is negative for expense/fee per the F-02 generated column.
    expense_stmt = (
        select(
            func.coalesce(
                func.sum(func.abs(FinancialTransaction.signed_amount)),
                Decimal("0"),
            ),
            func.count(),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(list(EXPENSE_TYPES)),
            FinancialTransaction.status.in_(posted_statuses),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    expense_row = (await db.execute(expense_stmt)).one()
    monthly_expenses: Decimal = Decimal(str(expense_row[0]))
    expense_count: int = expense_row[1] or 0

    # Pending totals (tracked separately; signed_amount is forced to 0 when
    # status='pending' by the F-08 generated column, so we can't rely on that).
    pending_income_stmt = (
        select(
            func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0"))
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(list(INCOME_TYPES)),
            FinancialTransaction.status == FinancialTransactionStatus.PENDING,
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    pending_income = Decimal(
        str((await db.execute(pending_income_stmt)).scalar_one())
    )

    pending_expense_stmt = (
        select(
            func.coalesce(func.sum(FinancialTransaction.amount), Decimal("0"))
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(list(EXPENSE_TYPES)),
            FinancialTransaction.status == FinancialTransactionStatus.PENDING,
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    pending_expenses = Decimal(
        str((await db.execute(pending_expense_stmt)).scalar_one())
    )

    net_cashflow = monthly_income - monthly_expenses
    savings_rate: float | None = None
    if monthly_income > 0:
        savings_rate = float(net_cashflow / monthly_income)

    # burn_rate per spec: monthly_expenses / 30 (daily average)
    burn_rate = monthly_expenses / Decimal("30") if monthly_expenses else Decimal("0")

    days_in_period = (period_end - period_start).days + 1
    transaction_count = income_count + expense_count

    # Invariant D-01: DerivedExplanation with summary + factors.
    explanation = DerivedExplanation(
        summary=(
            f"Cashflow {period_start.isoformat()}→{period_end.isoformat()}: "
            f"income {monthly_income}, expenses {monthly_expenses}, "
            f"net {net_cashflow}. "
            f"Savings rate {savings_rate if savings_rate is not None else 'n/a'}. "
            f"Excludes transfer + investment types (F-07)."
        ),
        factors=[
            DerivedFactor(
                signal="monthly_income",
                value=str(monthly_income),
                weight=1.0,
            ),
            DerivedFactor(
                signal="monthly_expenses",
                value=str(monthly_expenses),
                weight=1.0,
            ),
            DerivedFactor(
                signal="net_cashflow", value=str(net_cashflow), weight=1.0
            ),
            DerivedFactor(
                signal="transaction_count", value=transaction_count, weight=1.0
            ),
            DerivedFactor(
                signal="pending_income", value=str(pending_income), weight=0.5
            ),
            DerivedFactor(
                signal="pending_expenses",
                value=str(pending_expenses),
                weight=0.5,
            ),
            DerivedFactor(
                signal="exclusion_rule",
                value="F-07: transfer_in/out, investment_buy/sell, adjustment",
                weight=1.0,
            ),
        ],
        confidence=None,
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "days_in_period": days_in_period,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "net_cashflow": net_cashflow,
        "savings_rate": savings_rate,
        "burn_rate": burn_rate,
        "pending_income": pending_income,
        "pending_expenses": pending_expenses,
        "transaction_count": transaction_count,
        "explanation": explanation,
    }
