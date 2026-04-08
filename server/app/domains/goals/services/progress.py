"""
Goal progress computation service (Section 2.4).

Invariants enforced:
- D-03: progress is non-canonical, recomputable from edges + task status
- S-01: progress is CACHED DERIVED
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import GoalNode, TaskNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import EdgeRelationType, EdgeState, TaskStatus


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
