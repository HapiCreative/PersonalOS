"""
Daily plans temporal service (Section 3, TABLE 22).
One plan per user per date. First commit wins; subsequent edits update in place.

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-04: Ownership alignment (user_id must match task owner_id).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.temporal.models import DailyPlan
from server.app.core.models.node import Node, TaskNode
from server.app.core.models.enums import NodeType, TaskStatus


async def get_daily_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date,
) -> DailyPlan | None:
    """Get the daily plan for a specific date."""
    stmt = select(DailyPlan).where(
        DailyPlan.user_id == user_id,
        DailyPlan.date == plan_date,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_daily_plan_by_id(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> DailyPlan | None:
    """Get a daily plan by ID, enforcing ownership (Invariant T-04)."""
    stmt = select(DailyPlan).where(
        DailyPlan.id == plan_id,
        DailyPlan.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_daily_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date,
    selected_task_ids: list[uuid.UUID],
    intention_text: str | None = None,
) -> DailyPlan:
    """
    Create or update a daily plan for a given date.
    First commit creates; subsequent calls update in place.

    Invariant T-04: Validates that all selected task IDs belong to the user.
    """
    # Invariant T-04: Verify all task IDs belong to user and are valid tasks
    if selected_task_ids:
        stmt = (
            select(Node.id)
            .join(TaskNode, TaskNode.node_id == Node.id)
            .where(
                Node.id.in_(selected_task_ids),
                Node.owner_id == user_id,
                Node.type == NodeType.TASK,
                Node.archived_at.is_(None),
                TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            )
        )
        result = await db.execute(stmt)
        valid_ids = {row[0] for row in result.all()}
        invalid_ids = set(selected_task_ids) - valid_ids
        if invalid_ids:
            raise ValueError(
                f"Invalid task IDs (not found, not owned, archived, or completed): "
                f"{[str(tid) for tid in invalid_ids]}"
            )

    # Check if plan already exists for this date (first commit wins, subsequent updates)
    existing = await get_daily_plan(db, user_id, plan_date)

    if existing is not None:
        # Update existing plan in place
        existing.selected_task_ids = selected_task_ids
        if intention_text is not None:
            existing.intention_text = intention_text
        await db.flush()
        return existing

    # Create new plan
    plan = DailyPlan(
        user_id=user_id,
        date=plan_date,
        selected_task_ids=selected_task_ids,
        intention_text=intention_text,
        created_at=datetime.now(timezone.utc),
    )
    db.add(plan)
    await db.flush()
    return plan


async def close_daily_plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date,
) -> DailyPlan | None:
    """
    Close a daily plan (evening reflection).
    Sets closed_at timestamp.
    """
    plan = await get_daily_plan(db, user_id, plan_date)
    if plan is None:
        return None

    plan.closed_at = datetime.now(timezone.utc)
    await db.flush()
    return plan


async def list_daily_plans(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[DailyPlan], int]:
    """List daily plans for a user, most recent first."""
    from sqlalchemy import func

    count_stmt = (
        select(func.count())
        .select_from(DailyPlan)
        .where(DailyPlan.user_id == user_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(DailyPlan)
        .where(DailyPlan.user_id == user_id)
        .order_by(DailyPlan.date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    plans = list(result.scalars().all())

    return plans, total
