"""
Goal domain service (Section 2.4, 8.1).
Handles goal CRUD and progress computation.

Invariants enforced:
- D-03: progress is non-canonical, recomputable from edges + task status
- S-01: progress is CACHED DERIVED
- B-04: Background job ownership scope
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, GoalNode, TaskNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, GoalStatus, EdgeRelationType, EdgeState, TaskStatus,
)


async def compute_goal_progress(
    db: AsyncSession,
    goal_node_id: uuid.UUID,
) -> float:
    """
    Compute goal progress as weighted sum of completed tasks via goal_tracks_task edges.
    All weights = 1.0 for MVP.

    Invariant D-03: This is a derived computation, non-canonical.
    Progress = (completed tasks) / (total linked tasks), or 0 if no linked tasks.
    """
    # Find all active goal_tracks_task edges from this goal
    stmt = (
        select(Edge.target_id, Edge.weight, TaskNode.status)
        .join(TaskNode, TaskNode.node_id == Edge.target_id)
        .where(
            Edge.source_id == goal_node_id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    if not rows:
        return 0.0

    total_weight = sum(row.weight for row in rows)
    if total_weight == 0:
        return 0.0

    completed_weight = sum(
        row.weight for row in rows
        if row.status == TaskStatus.DONE
    )

    return min(completed_weight / total_weight, 1.0)


async def refresh_goal_progress(
    db: AsyncSession,
    goal_node_id: uuid.UUID,
) -> float:
    """Recompute and persist goal progress. Invariant D-03: Non-canonical cache refresh."""
    progress = await compute_goal_progress(db, goal_node_id)

    stmt = select(GoalNode).where(GoalNode.node_id == goal_node_id)
    result = await db.execute(stmt)
    goal = result.scalar_one_or_none()
    if goal:
        goal.progress = progress
        await db.flush()

    return progress


async def create_goal(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    status: GoalStatus = GoalStatus.ACTIVE,
    start_date: date | None = None,
    end_date: date | None = None,
    timeframe_label: str | None = None,
    milestones: list[dict] | None = None,
    notes: str | None = None,
) -> tuple[Node, GoalNode]:
    """Create a goal (Core node + goal_nodes companion)."""
    node = Node(
        type=NodeType.GOAL,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    goal = GoalNode(
        node_id=node.id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        timeframe_label=timeframe_label,
        # Invariant D-03: progress starts at 0.0, non-canonical
        progress=0.0,
        milestones=milestones or [],
        notes=notes,
    )
    db.add(goal)
    await db.flush()

    return node, goal


async def get_goal(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, GoalNode] | None:
    """Get a goal by node ID, enforcing ownership."""
    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, goal = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, goal


async def list_goals(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: GoalStatus | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, GoalNode]], int]:
    """List goals with optional filters, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.GOAL]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if status:
        base_filter.append(GoalNode.status == status)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(GoalNode.end_date.asc().nullslast(), Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_goal(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    status: GoalStatus | None = None,
    start_date: date | None = ...,  # type: ignore[assignment]
    end_date: date | None = ...,  # type: ignore[assignment]
    timeframe_label: str | None = ...,  # type: ignore[assignment]
    milestones: list[dict] | None = None,
    notes: str | None = ...,  # type: ignore[assignment]
) -> tuple[Node, GoalNode] | None:
    """Update goal fields, enforcing ownership."""
    pair = await get_goal(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, goal = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if status is not None:
        goal.status = status
    if start_date is not ...:
        goal.start_date = start_date
    if end_date is not ...:
        goal.end_date = end_date
    if timeframe_label is not ...:
        goal.timeframe_label = timeframe_label
    if milestones is not None:
        goal.milestones = milestones
    if notes is not ...:
        goal.notes = notes

    await db.flush()
    return node, goal


async def get_goal_linked_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_node_id: uuid.UUID,
) -> list[dict]:
    """
    Get tasks linked to a goal via goal_tracks_task edges.
    Returns task info + edge info for display.
    """
    stmt = (
        select(Node, TaskNode, Edge)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .join(Edge, Edge.target_id == Node.id)
        .where(
            Edge.source_id == goal_node_id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
        )
        .order_by(TaskNode.due_date.asc().nullslast(), Node.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    return [
        {
            "node_id": node.id,
            "title": node.title,
            "status": task.status.value,
            "priority": task.priority.value,
            "due_date": task.due_date,
            "is_recurring": task.is_recurring,
            "edge_id": edge.id,
            "edge_weight": edge.weight,
        }
        for node, task, edge in rows
    ]
