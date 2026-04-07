"""
Progress intelligence service (Section 4 — Derived Layer).

Tracks three metrics for goals and tasks:
- Momentum: weighted tasks completed per week (rolling 4-week avg from task_execution_events)
- Consistency streak: consecutive days with progress
- Drift score: 0=on track, 1=abandoned, based on time since last progress

Refresh schedule:
- momentum + streak: daily
- progress: on execution event

Invariant D-02: Fully recomputable from task_execution_events + edges.
Invariant D-03: Non-canonical, stored in progress_intelligence table.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, GoalNode, TaskNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, GoalStatus, TaskStatus, EdgeRelationType, EdgeState,
    TaskExecutionEventType,
)
from server.app.temporal.models import TaskExecutionEvent
from server.app.derived.models import ProgressIntelligence

# Drift thresholds (days since last progress)
DRIFT_THRESHOLD_DAYS = 30  # after 30 days with no progress → drift = 1.0
DRIFT_MILD_DAYS = 7  # after 7 days → drift starts increasing


def _compute_drift_score(last_progress_at: datetime | None, now: datetime) -> float:
    """
    Compute drift score (0=on track, 1=abandoned).
    Linear ramp from DRIFT_MILD_DAYS to DRIFT_THRESHOLD_DAYS.
    Invariant D-02: Recomputable from last progress timestamp.
    """
    if last_progress_at is None:
        return 1.0  # No progress ever recorded

    delta_days = (now - last_progress_at).total_seconds() / 86400.0
    if delta_days <= DRIFT_MILD_DAYS:
        return 0.0
    if delta_days >= DRIFT_THRESHOLD_DAYS:
        return 1.0
    # Linear interpolation between mild and threshold
    return (delta_days - DRIFT_MILD_DAYS) / (DRIFT_THRESHOLD_DAYS - DRIFT_MILD_DAYS)


async def _compute_momentum(
    db: AsyncSession,
    task_ids: list[uuid.UUID],
    now: datetime,
) -> float:
    """
    Momentum: weighted tasks completed per week, rolling 4-week average.
    Each week gets decreasing weight: [1.0, 0.75, 0.5, 0.25] (most recent first).
    Invariant D-02: Recomputable from task_execution_events.
    """
    if not task_ids:
        return 0.0

    week_weights = [1.0, 0.75, 0.5, 0.25]
    weighted_sum = 0.0
    total_weight = sum(week_weights)

    for i, weight in enumerate(week_weights):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(weeks=1)

        stmt = select(func.count()).select_from(TaskExecutionEvent).where(
            TaskExecutionEvent.task_id.in_(task_ids),
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.created_at >= week_start,
            TaskExecutionEvent.created_at < week_end,
            TaskExecutionEvent.node_deleted == False,
        )
        count = (await db.execute(stmt)).scalar_one()
        weighted_sum += weight * count

    return weighted_sum / total_weight if total_weight > 0 else 0.0


async def _compute_consistency_streak(
    db: AsyncSession,
    task_ids: list[uuid.UUID],
    today: date,
) -> int:
    """
    Consistency streak: consecutive days with at least one completion event.
    Counts backwards from today.
    Invariant D-02: Recomputable from task_execution_events.
    """
    if not task_ids:
        return 0

    streak = 0
    check_date = today

    for _ in range(365):  # Max 1 year lookback
        stmt = select(func.count()).select_from(TaskExecutionEvent).where(
            TaskExecutionEvent.task_id.in_(task_ids),
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.expected_for_date == check_date,
            TaskExecutionEvent.node_deleted == False,
        )
        count = (await db.execute(stmt)).scalar_one()
        if count > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak


async def _get_last_progress_at(
    db: AsyncSession,
    task_ids: list[uuid.UUID],
) -> datetime | None:
    """Get the timestamp of the most recent completed execution event."""
    if not task_ids:
        return None

    stmt = (
        select(TaskExecutionEvent.created_at)
        .where(
            TaskExecutionEvent.task_id.in_(task_ids),
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.node_deleted == False,
        )
        .order_by(TaskExecutionEvent.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return row


async def _compute_goal_progress(
    db: AsyncSession,
    goal_node_id: uuid.UUID,
) -> float:
    """
    Compute goal progress as weighted sum of completed tasks via goal_tracks_task edges.
    All weights = 1.0 for MVP.
    Invariant D-02: Recomputable from edges + task_nodes status.
    """
    # Get all tasks linked via goal_tracks_task edges
    stmt = (
        select(Edge.target_id, Edge.weight)
        .where(
            Edge.source_id == goal_node_id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    task_edges = list(result.all())

    if not task_edges:
        return 0.0

    total_weight = 0.0
    completed_weight = 0.0

    for task_id, weight in task_edges:
        task_result = await db.execute(
            select(TaskNode.status).where(TaskNode.node_id == task_id)
        )
        task_status = task_result.scalar_one_or_none()
        if task_status is None:
            continue

        total_weight += weight
        if task_status == TaskStatus.DONE:
            completed_weight += weight

    if total_weight == 0:
        return 0.0

    return completed_weight / total_weight


async def compute_progress_intelligence(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> ProgressIntelligence | None:
    """
    Compute and persist progress intelligence for a node (goal or task).

    Invariant D-02: All metrics are recomputed from Core + Temporal data.
    Invariant D-03: Result stored in progress_intelligence (non-canonical).
    """
    # Fetch node with ownership check
    stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    if node is None:
        return None

    now = datetime.now(timezone.utc)
    today = date.today()
    progress = 0.0
    task_ids: list[uuid.UUID] = []

    if node.type == NodeType.GOAL:
        # For goals: get linked task IDs and compute goal progress
        progress = await _compute_goal_progress(db, node_id)

        # Get task IDs linked via goal_tracks_task
        edge_stmt = select(Edge.target_id).where(
            Edge.source_id == node_id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
        )
        edge_result = await db.execute(edge_stmt)
        task_ids = [row[0] for row in edge_result.all()]

        # Also update the cached progress on goal_nodes (Invariant D-03)
        goal_result = await db.execute(
            select(GoalNode).where(GoalNode.node_id == node_id)
        )
        goal = goal_result.scalar_one_or_none()
        if goal:
            goal.progress = progress

    elif node.type == NodeType.TASK:
        # For tasks: momentum/streak based on this task's execution events
        task_ids = [node_id]

        task_result = await db.execute(
            select(TaskNode).where(TaskNode.node_id == node_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            progress = 1.0 if task.status == TaskStatus.DONE else 0.0
    else:
        # Progress intelligence is primarily for goals and tasks
        return None

    # Compute metrics
    momentum = await _compute_momentum(db, task_ids, now)
    streak = await _compute_consistency_streak(db, task_ids, today)
    last_progress = await _get_last_progress_at(db, task_ids)
    if last_progress and last_progress.tzinfo is None:
        last_progress = last_progress.replace(tzinfo=timezone.utc)
    drift = _compute_drift_score(last_progress, now)

    # Upsert progress_intelligence record
    existing = await db.execute(
        select(ProgressIntelligence).where(ProgressIntelligence.node_id == node_id)
    )
    pi = existing.scalar_one_or_none()

    if pi is None:
        pi = ProgressIntelligence(
            node_id=node_id,
            progress=progress,
            momentum=momentum,
            consistency_streak=streak,
            drift_score=drift,
            last_progress_at=last_progress,
            computed_at=now,
        )
        db.add(pi)
    else:
        pi.progress = progress
        pi.momentum = momentum
        pi.consistency_streak = streak
        pi.drift_score = drift
        pi.last_progress_at = last_progress
        pi.computed_at = now

    await db.flush()
    return pi


async def compute_progress_batch(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_type: NodeType | None = None,
    limit: int = 50,
) -> list[ProgressIntelligence]:
    """
    Batch compute progress intelligence for goals and/or tasks.
    Invariant D-02: All results are recomputable.
    """
    filters = [Node.owner_id == owner_id, Node.archived_at.is_(None)]

    if node_type:
        filters.append(Node.type == node_type)
    else:
        filters.append(Node.type.in_([NodeType.GOAL, NodeType.TASK]))

    stmt = select(Node.id).where(*filters).order_by(Node.updated_at.desc()).limit(limit)
    result = await db.execute(stmt)
    node_ids = [row[0] for row in result.all()]

    results = []
    for nid in node_ids:
        pi = await compute_progress_intelligence(db, owner_id, nid)
        if pi:
            results.append(pi)

    return results


async def get_progress_intelligence(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> ProgressIntelligence | None:
    """Get cached progress intelligence for a node."""
    result = await db.execute(
        select(ProgressIntelligence).where(ProgressIntelligence.node_id == node_id)
    )
    return result.scalar_one_or_none()
