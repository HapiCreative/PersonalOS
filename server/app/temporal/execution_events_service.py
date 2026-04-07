"""
Task execution events temporal service (Section 3.7, 8.1).
Unified execution log for all tasks (recurring and non-recurring).

Invariants enforced:
- S-03: Completion state derivation (non-recurring → done on completed event)
- S-04: Execution event uniqueness (one terminal event per task per date)
- T-01: No temporal-to-temporal FKs
- T-02: Append-only event records
- T-04: Ownership alignment
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode
from server.app.core.models.enums import NodeType, TaskStatus, TaskExecutionEventType
from server.app.temporal.models import TaskExecutionEvent


async def create_execution_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
    event_type: TaskExecutionEventType,
    expected_for_date: date,
    notes: str | None = None,
) -> TaskExecutionEvent:
    """
    Record a task execution event.

    Invariant T-04: Ownership alignment - user_id must match task owner_id.
    Invariant S-04: At most one terminal event per task per date.
    Invariant S-03: Non-recurring tasks transition to done on completed event.
    Invariant T-02: Append-only - we only create, never update.
    """
    # Verify task exists and enforce ownership (T-04)
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.id == task_id,
            Node.owner_id == user_id,
            Node.type == NodeType.TASK,
        )
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        raise ValueError("Task not found or not owned by user (Invariant T-04)")

    node, task = row

    # Invariant S-04: Check uniqueness - at most one terminal event per task per date
    existing_stmt = select(TaskExecutionEvent).where(
        TaskExecutionEvent.task_id == task_id,
        TaskExecutionEvent.expected_for_date == expected_for_date,
        TaskExecutionEvent.node_deleted == False,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise ValueError(
            f"Invariant S-04: Terminal event already exists for task {task_id} "
            f"on {expected_for_date} (event_type={existing.event_type.value}). "
            f"Override requires explicit reversal."
        )

    # Create the event (T-02: append-only)
    event = TaskExecutionEvent(
        task_id=task_id,
        user_id=user_id,
        event_type=event_type,
        expected_for_date=expected_for_date,
        notes=notes,
    )
    db.add(event)
    await db.flush()

    # Invariant S-03: Completion state derivation
    # Non-recurring: status transitions to done when completed event exists
    # Recurring: completed event does NOT change status
    if event_type == TaskExecutionEventType.COMPLETED and not task.is_recurring:
        task.status = TaskStatus.DONE
        await db.flush()

    return event


async def list_execution_events(
    db: AsyncSession,
    user_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    expected_for_date: date | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TaskExecutionEvent], int]:
    """
    List execution events, enforcing ownership via user_id.
    Invariant T-04: All queries scoped to user.
    """
    base_filter = [TaskExecutionEvent.user_id == user_id]

    if not include_deleted:
        base_filter.append(TaskExecutionEvent.node_deleted == False)
    if task_id:
        base_filter.append(TaskExecutionEvent.task_id == task_id)
    if expected_for_date:
        base_filter.append(TaskExecutionEvent.expected_for_date == expected_for_date)

    count_stmt = (
        select(func.count())
        .select_from(TaskExecutionEvent)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(TaskExecutionEvent)
        .where(*base_filter)
        .order_by(TaskExecutionEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    events = list(result.scalars().all())

    return events, total


async def get_execution_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    event_id: uuid.UUID,
) -> TaskExecutionEvent | None:
    """Get a single execution event by ID, enforcing ownership."""
    stmt = select(TaskExecutionEvent).where(
        TaskExecutionEvent.id == event_id,
        TaskExecutionEvent.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
