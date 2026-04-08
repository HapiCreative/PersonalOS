"""Allocation and goal financial extension service functions for the finance domain."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    AllocationType,
    EdgeOrigin,
    EdgeRelationType,
    EdgeState,
    GoalType,
)
from server.app.core.models.node import AccountNode, GoalAllocation, GoalNode, Node


async def create_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_id: uuid.UUID,
    account_id: uuid.UUID,
    allocation_type: AllocationType,
    value: Decimal,
) -> GoalAllocation:
    """
    Create a goal allocation.
    Invariant F-06: No shadow graph — relationships are edges + allocations only.
    Invariant F-13: For percentage allocations, SUM ≤ 1.0 per account across all goals.

    Also ensures that a corresponding account_funds_goal edge exists (F-06).
    """
    # Validate goal exists and is financial, owned by user
    goal_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(Node.id == goal_id, Node.owner_id == owner_id)
    )
    goal_result = await db.execute(goal_stmt)
    goal_row = goal_result.one_or_none()
    if goal_row is None:
        raise ValueError(f"Goal {goal_id} not found or not owned by user")

    _, goal_node = goal_row
    # Invariant F-03: allocation only makes sense for financial goals
    if goal_node.goal_type != GoalType.FINANCIAL:
        raise ValueError("Invariant F-03: Allocations can only be created for financial goals")

    # Validate account exists and is owned by user
    acct_stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(Node.id == account_id, Node.owner_id == owner_id)
    )
    acct_result = await db.execute(acct_stmt)
    acct_row = acct_result.one_or_none()
    if acct_row is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Validate value constraints
    if allocation_type == AllocationType.PERCENTAGE:
        if value < 0 or value > 1:
            raise ValueError("Percentage allocation value must be between 0.0 and 1.0")

        # Invariant F-13: Check sum of percentage allocations for this account
        sum_stmt = (
            select(func.coalesce(func.sum(GoalAllocation.value), Decimal("0")))
            .where(
                GoalAllocation.account_id == account_id,
                GoalAllocation.allocation_type == AllocationType.PERCENTAGE,
            )
        )
        current_sum = (await db.execute(sum_stmt)).scalar_one()
        if current_sum + value > Decimal("1.0"):
            raise ValueError(
                f"Invariant F-13: Percentage allocation sum for account {account_id} "
                f"would exceed 1.0 (current: {current_sum}, adding: {value})"
            )
    elif allocation_type == AllocationType.FIXED:
        if value < 0:
            raise ValueError("Fixed allocation value must be non-negative")

    # Invariant F-06: Ensure account_funds_goal edge exists; create if not
    edge_stmt = select(Edge).where(
        Edge.source_id == account_id,
        Edge.target_id == goal_id,
        Edge.relation_type == EdgeRelationType.ACCOUNT_FUNDS_GOAL,
    )
    existing_edge = (await db.execute(edge_stmt)).scalar_one_or_none()
    if existing_edge is None:
        edge = Edge(
            source_id=account_id,
            target_id=goal_id,
            relation_type=EdgeRelationType.ACCOUNT_FUNDS_GOAL,
            origin=EdgeOrigin.SYSTEM,
            state=EdgeState.ACTIVE,
            weight=1.0,
            metadata_={},
        )
        db.add(edge)

    allocation = GoalAllocation(
        goal_id=goal_id,
        account_id=account_id,
        allocation_type=allocation_type,
        value=value,
    )
    db.add(allocation)
    await db.flush()

    return allocation


async def get_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
) -> GoalAllocation | None:
    """Get an allocation by ID, enforcing ownership through the goal node."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.goal_id)
        .where(
            GoalAllocation.id == allocation_id,
            Node.owner_id == owner_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_allocations_for_goal(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_id: uuid.UUID,
) -> list[GoalAllocation]:
    """List all allocations for a goal, enforcing ownership."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.goal_id)
        .where(
            GoalAllocation.goal_id == goal_id,
            Node.owner_id == owner_id,
        )
        .order_by(GoalAllocation.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_allocations_for_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
) -> list[GoalAllocation]:
    """List all allocations for an account, enforcing ownership."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.account_id)
        .where(
            GoalAllocation.account_id == account_id,
            Node.owner_id == owner_id,
        )
        .order_by(GoalAllocation.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
    allocation_type: AllocationType | None = None,
    value: Decimal | None = None,
) -> GoalAllocation | None:
    """
    Update an allocation. Re-validates F-13 bounds on change.
    """
    alloc = await get_allocation(db, owner_id, allocation_id)
    if alloc is None:
        return None

    new_type = allocation_type or alloc.allocation_type
    new_value = value if value is not None else alloc.value

    if new_type == AllocationType.PERCENTAGE:
        if new_value < 0 or new_value > 1:
            raise ValueError("Percentage allocation value must be between 0.0 and 1.0")

        # Invariant F-13: Check sum excluding current allocation
        sum_stmt = (
            select(func.coalesce(func.sum(GoalAllocation.value), Decimal("0")))
            .where(
                GoalAllocation.account_id == alloc.account_id,
                GoalAllocation.allocation_type == AllocationType.PERCENTAGE,
                GoalAllocation.id != allocation_id,
            )
        )
        current_sum = (await db.execute(sum_stmt)).scalar_one()
        if current_sum + new_value > Decimal("1.0"):
            raise ValueError(
                f"Invariant F-13: Percentage allocation sum for account {alloc.account_id} "
                f"would exceed 1.0 (other: {current_sum}, new: {new_value})"
            )
    elif new_type == AllocationType.FIXED:
        if new_value < 0:
            raise ValueError("Fixed allocation value must be non-negative")

    if allocation_type is not None:
        alloc.allocation_type = allocation_type
    if value is not None:
        alloc.value = value

    alloc.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return alloc


async def delete_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
) -> bool:
    """Delete an allocation. Cleans up orphaned account_funds_goal edges."""
    alloc = await get_allocation(db, owner_id, allocation_id)
    if alloc is None:
        return False

    goal_id = alloc.goal_id
    account_id = alloc.account_id

    await db.delete(alloc)
    await db.flush()

    # Check if any other allocations remain for this account-goal pair
    remaining_stmt = select(func.count()).where(
        GoalAllocation.goal_id == goal_id,
        GoalAllocation.account_id == account_id,
    )
    remaining = (await db.execute(remaining_stmt)).scalar_one()

    # If no more allocations, remove the account_funds_goal edge
    if remaining == 0:
        edge_stmt = select(Edge).where(
            Edge.source_id == account_id,
            Edge.target_id == goal_id,
            Edge.relation_type == EdgeRelationType.ACCOUNT_FUNDS_GOAL,
        )
        edge = (await db.execute(edge_stmt)).scalar_one_or_none()
        if edge:
            await db.delete(edge)
            await db.flush()

    return True


async def validate_goal_financial_fields(
    goal_type: GoalType,
    target_amount: Decimal | None,
    currency: str | None,
) -> None:
    """
    Invariant F-03: Financial goal field consistency.
    - financial: target_amount and currency must be non-null
    - general: all financial fields must be null
    Application layer enforcement (primary).
    """
    if goal_type == GoalType.FINANCIAL:
        if target_amount is None or currency is None:
            raise ValueError(
                "Invariant F-03: Financial goals require target_amount and currency to be non-null"
            )
    elif goal_type == GoalType.GENERAL:
        if target_amount is not None or currency is not None:
            raise ValueError(
                "Invariant F-03: General goals require target_amount and currency to be null"
            )


async def update_goal_financial(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_node_id: uuid.UUID,
    goal_type: GoalType,
    target_amount: Decimal | None = None,
    currency: str | None = None,
) -> tuple[Node, GoalNode] | None:
    """
    Update goal financial fields with F-03 validation.
    Invariant F-03: Financial goals require target_amount + currency;
                    general goals require all financial fields null.
    """
    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(Node.id == goal_node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, goal = row

    # Invariant F-03: Validate field consistency
    await validate_goal_financial_fields(goal_type, target_amount, currency)

    goal.goal_type = goal_type
    goal.target_amount = target_amount
    goal.currency = currency

    # If switching to general, clear current_amount too
    if goal_type == GoalType.GENERAL:
        goal.current_amount = None

    node.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return node, goal
