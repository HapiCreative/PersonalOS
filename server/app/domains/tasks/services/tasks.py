"""
Task domain service (Section 2.4, 8.1).
Handles task CRUD, state machine transitions, and recurring task logic.

Invariants enforced:
- S-02: Recurring task + done = invalid
- S-03: Completion state derivation
- B-03: State machine transitions
- B-04: Background job ownership scope
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode
from server.app.core.models.enums import NodeType, TaskStatus, TaskPriority


# Invariant B-03: Valid state transitions
# todo -> in_progress -> done (non-recurring only)
# todo -> cancelled, in_progress -> cancelled
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.TODO: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {TaskStatus.DONE, TaskStatus.CANCELLED},
    TaskStatus.DONE: set(),       # Terminal state
    TaskStatus.CANCELLED: set(),  # Terminal state
}


def validate_transition(
    current_status: TaskStatus,
    new_status: TaskStatus,
    is_recurring: bool,
) -> str | None:
    """
    Validate a task status transition.
    Returns None if valid, error message if invalid.

    Invariant B-03: State machine transitions.
    Invariant S-02: Recurring task + done = invalid.
    """
    # Invariant S-02: Recurring task + done = invalid
    if is_recurring and new_status == TaskStatus.DONE:
        return (
            "Invariant S-02: Cannot set recurring task to done. "
            "Remove recurrence first, or cancel the task."
        )

    # Invariant B-03: State machine transitions
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return (
            f"Invariant B-03: Invalid transition from {current_status.value} "
            f"to {new_status.value}. Allowed: {[s.value for s in allowed]}"
        )

    return None


def _compute_word_count(text: str) -> int:
    """Compute word count for content."""
    return len(text.split()) if text.strip() else 0


async def create_task(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    status: TaskStatus = TaskStatus.TODO,
    priority: TaskPriority = TaskPriority.MEDIUM,
    due_date: date | None = None,
    recurrence: str | None = None,
    notes: str | None = None,
) -> tuple[Node, TaskNode]:
    """Create a task (Core node + task_nodes companion)."""
    # Invariant S-02: Prevent creation with recurring + done
    if recurrence is not None and status == TaskStatus.DONE:
        raise ValueError("Invariant S-02: Cannot create a recurring task with status done.")

    # Create the Core node
    node = Node(
        type=NodeType.TASK,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    # Create the companion table record
    task = TaskNode(
        node_id=node.id,
        status=status,
        priority=priority,
        due_date=due_date,
        recurrence=recurrence,
        # Invariant S-01: CACHED DERIVED is_recurring
        is_recurring=recurrence is not None,
        notes=notes,
    )
    db.add(task)
    await db.flush()

    return node, task


async def get_task(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, TaskNode] | None:
    """Get a task by node ID, enforcing ownership."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, task = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, task


async def list_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, TaskNode]], int]:
    """List tasks with optional filters, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.TASK]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if status:
        base_filter.append(TaskNode.status == status)
    if priority:
        base_filter.append(TaskNode.priority == priority)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(TaskNode.due_date.asc().nullslast(), Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_task(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    priority: TaskPriority | None = None,
    due_date: date | None = ...,  # type: ignore[assignment]
    recurrence: str | None = ...,  # type: ignore[assignment]
    notes: str | None = ...,  # type: ignore[assignment]
) -> tuple[Node, TaskNode] | None:
    """Update task fields, enforcing ownership."""
    pair = await get_task(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, task = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if priority is not None:
        task.priority = priority
    if due_date is not ...:
        task.due_date = due_date
    if recurrence is not ...:
        task.recurrence = recurrence
        # Invariant S-01: CACHED DERIVED is_recurring
        task.is_recurring = recurrence is not None
        # Invariant S-02: If setting recurrence on a done task, reject
        if recurrence is not None and task.status == TaskStatus.DONE:
            raise ValueError("Invariant S-02: Cannot set recurrence on a done task.")
    if notes is not ...:
        task.notes = notes

    await db.flush()
    return node, task


async def transition_task(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    new_status: TaskStatus,
) -> tuple[Node, TaskNode]:
    """
    Transition task status with state machine validation.
    Invariant B-03: State machine transitions.
    Invariant S-02: Recurring task + done = invalid.
    """
    pair = await get_task(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        raise ValueError("Task not found")

    node, task = pair

    error = validate_transition(task.status, new_status, task.is_recurring)
    if error:
        raise ValueError(error)

    task.status = new_status
    await db.flush()
    return node, task
