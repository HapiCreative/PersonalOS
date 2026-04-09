"""
Finance Phase F2-C — Financial Goal Progress (Derived layer).

Ref: Finance Design Rev 3 Section 4.4.

Metrics per financial goal:
- current_amount = SUM(account_balance × allocation) across goal_allocations
- progress_pct = current_amount / target_amount × 100
- monthly_contribution_rate = linear projection from last 90 days
- projected_completion_date = linear projection
- monthly_contribution_needed = (target_amount - current_amount) / months_remaining

Background job `refresh_all_goal_progress` updates goal_nodes.current_amount
(CACHED DERIVED per Invariant S-01). The derived computation here is the
source of truth; the column is for display performance only.

Invariants:
- F-03: Only GoalType.FINANCIAL goals considered.
- F-06: Allocations via goal_allocations, not shadow fields.
- F-07: Cashflow exclusion rule applies when counting contributions.
- D-01: DerivedExplanation on every output.
- D-02: Every output recomputable.
- S-01: goal_nodes.current_amount is CACHED DERIVED.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    AllocationType,
    FinancialTransactionStatus,
    FinancialTransactionType,
    GoalType,
    NodeType,
)
from server.app.core.models.node import (
    FinancialTransaction,
    GoalAllocation,
    GoalNode,
    Node,
)
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
    utc_now,
)
from server.app.domains.finance.services.balance import compute_account_balance


# Transactions that count as "contributions" to a financial goal when summed
# across allocated accounts. Uses the same cashflow-eligible inflow types
# (income/dividend/interest/refund) plus positive transfers-in.
CONTRIBUTION_INCOME_TYPES = [
    FinancialTransactionType.INCOME,
    FinancialTransactionType.DIVIDEND,
    FinancialTransactionType.INTEREST,
    FinancialTransactionType.REFUND,
    FinancialTransactionType.TRANSFER_IN,
]


async def _apply_allocation(
    balance: Decimal,
    allocation_type: AllocationType,
    allocation_value: Decimal,
) -> Decimal:
    """
    Invariant F-06: allocation value is canonical. Percentage is 0.0–1.0
    (F-13 bounds); fixed is an absolute currency amount.
    """
    if allocation_type == AllocationType.PERCENTAGE:
        return balance * allocation_value
    # Fixed allocation is capped at the actual balance.
    return min(balance, allocation_value)


async def _sum_recent_contributions(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_ids: list[uuid.UUID],
    since: date,
) -> Decimal:
    """
    Sum signed inflows (Invariant F-07 compatible income-side types plus
    transfer_in) across the allocated accounts since `since` — used for the
    linear 90-day contribution rate.
    """
    if not account_ids:
        return Decimal("0")
    stmt = (
        select(func.coalesce(func.sum(FinancialTransaction.signed_amount), Decimal("0")))
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.account_id.in_(account_ids),
            FinancialTransaction.transaction_type.in_(CONTRIBUTION_INCOME_TYPES),
            FinancialTransaction.status.in_([
                FinancialTransactionStatus.POSTED,
                FinancialTransactionStatus.SETTLED,
            ]),
            FinancialTransaction.occurred_at >= datetime_at_start_of_day(since),
        )
    )
    total = (await db.execute(stmt)).scalar_one()
    return Decimal(str(total))


async def compute_goal_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    as_of_date: date | None = None,
) -> dict | None:
    """
    Section 4.4: Compute progress metrics for a single financial goal.
    Returns None if the goal is missing, not financial, or not owned by user.
    Invariant F-03: only financial goals produce results.
    """
    if as_of_date is None:
        as_of_date = date.today()

    goal_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.id == goal_id,
            Node.owner_id == user_id,
            Node.type == NodeType.GOAL,
        )
    )
    row = (await db.execute(goal_stmt)).one_or_none()
    if row is None:
        return None

    node, goal_node = row
    if goal_node.goal_type != GoalType.FINANCIAL:
        return None
    # Invariant F-03: financial goals require target_amount + currency
    if goal_node.target_amount is None or goal_node.currency is None:
        return None

    target_amount = Decimal(str(goal_node.target_amount))
    currency = goal_node.currency

    # Load allocations for this goal.
    allocs_stmt = select(GoalAllocation).where(GoalAllocation.goal_id == goal_id)
    allocations = list((await db.execute(allocs_stmt)).scalars().all())

    # current_amount = SUM(account_balance × allocation)
    current_amount = Decimal("0")
    account_ids: list[uuid.UUID] = []
    for alloc in allocations:
        try:
            balance_info = await compute_account_balance(
                db, user_id, alloc.account_id, as_of_date=as_of_date
            )
        except ValueError:
            continue
        account_balance = Decimal(str(balance_info["balance"]))
        contribution = await _apply_allocation(
            account_balance,
            alloc.allocation_type,
            Decimal(str(alloc.value)),
        )
        current_amount += contribution
        account_ids.append(alloc.account_id)

    progress_pct = 0.0
    if target_amount > 0:
        progress_pct = float(current_amount / target_amount * Decimal("100"))

    # Linear 90-day contribution rate
    lookback_start = as_of_date - timedelta(days=90)
    recent_total = await _sum_recent_contributions(
        db, user_id, account_ids, lookback_start
    )
    monthly_contribution_rate: Decimal | None = None
    if recent_total > 0:
        monthly_contribution_rate = (recent_total / Decimal("90")) * Decimal("30")

    projected_completion_date: date | None = None
    if (
        monthly_contribution_rate is not None
        and monthly_contribution_rate > 0
        and current_amount < target_amount
    ):
        remaining = target_amount - current_amount
        months_to_complete = remaining / monthly_contribution_rate
        days_to_complete = int(months_to_complete * Decimal("30"))
        projected_completion_date = as_of_date + timedelta(days=days_to_complete)
    elif current_amount >= target_amount:
        projected_completion_date = as_of_date

    days_remaining: int | None = None
    monthly_contribution_needed: Decimal | None = None
    is_on_track: bool | None = None
    if goal_node.end_date is not None:
        days_remaining = (goal_node.end_date - as_of_date).days
        if days_remaining > 0:
            months_until_deadline = Decimal(str(days_remaining)) / Decimal("30")
            if months_until_deadline > 0 and current_amount < target_amount:
                monthly_contribution_needed = (
                    target_amount - current_amount
                ) / months_until_deadline
        if (
            monthly_contribution_rate is not None
            and monthly_contribution_needed is not None
        ):
            is_on_track = monthly_contribution_rate >= monthly_contribution_needed
        elif current_amount >= target_amount:
            is_on_track = True

    explanation = DerivedExplanation(
        summary=(
            f"Goal '{node.title}': {current_amount}/{target_amount} {currency} "
            f"({progress_pct:.1f}%). "
            f"{len(allocations)} allocations, "
            f"monthly contribution rate "
            f"{monthly_contribution_rate if monthly_contribution_rate is not None else 'n/a'}."
        ),
        factors=[
            DerivedFactor(
                signal="current_amount", value=str(current_amount), weight=1.0
            ),
            DerivedFactor(
                signal="target_amount", value=str(target_amount), weight=1.0
            ),
            DerivedFactor(
                signal="progress_pct", value=progress_pct, weight=1.0
            ),
            DerivedFactor(
                signal="allocation_count", value=len(allocations), weight=0.8
            ),
            DerivedFactor(
                signal="contribution_lookback_days", value=90, weight=0.6
            ),
            DerivedFactor(
                signal="monthly_contribution_rate",
                value=str(monthly_contribution_rate)
                if monthly_contribution_rate is not None
                else None,
                weight=0.8,
            ),
        ],
        confidence=None,
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "goal_id": goal_id,
        "goal_name": node.title,
        "target_amount": target_amount,
        "current_amount": current_amount,
        "currency": currency,
        "progress_pct": progress_pct,
        "end_date": goal_node.end_date,
        "days_remaining": days_remaining,
        "monthly_contribution_rate": monthly_contribution_rate,
        "projected_completion_date": projected_completion_date,
        "monthly_contribution_needed": monthly_contribution_needed,
        "is_on_track": is_on_track,
        "allocation_count": len(allocations),
        "explanation": explanation,
    }


async def list_goal_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
) -> list[dict]:
    """Compute goal progress for every financial goal owned by user."""
    stmt = (
        select(Node.id)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == user_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.goal_type == GoalType.FINANCIAL,
        )
    )
    goal_ids = [row[0] for row in (await db.execute(stmt)).all()]

    results: list[dict] = []
    for gid in goal_ids:
        result = await compute_goal_progress(db, user_id, gid, as_of_date)
        if result is not None:
            results.append(result)
    return results


async def refresh_all_goal_progress(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
) -> int:
    """
    Background job: update goal_nodes.current_amount for every financial goal.

    Invariant S-01: current_amount is CACHED DERIVED — this function is the
    source-of-truth recomputation.
    """
    progresses = await list_goal_progress(db, user_id, as_of_date)
    updated = 0
    for progress in progresses:
        stmt = select(GoalNode).where(GoalNode.node_id == progress["goal_id"])
        goal_node = (await db.execute(stmt)).scalar_one_or_none()
        if goal_node is None:
            continue
        goal_node.current_amount = progress["current_amount"]
        updated += 1
    await db.flush()
    return updated
