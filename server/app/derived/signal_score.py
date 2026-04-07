"""
Signal score computation service (Section 4 — Derived Layer).

5-factor composite score for ranking and relevance:
- recency: 0.3 — How recently the node was updated
- link_density: 0.25 — Number of active edges (outgoing + incoming)
- completion_state: 0.2 — Task/goal completion status
- reference_frequency: 0.15 — Number of incoming references
- user_interaction: 0.1 — Recency of last_accessed_at

Invariant D-02: Fully recomputable from Core + Temporal data.
Invariant D-03: Non-canonical — stored in separate signal_scores table.
"""

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode, GoalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, TaskStatus, GoalStatus, EdgeState,
)
from server.app.derived.models import SignalScore

# Invariant D-02: Factor weights — recomputable, defined here as constants
WEIGHT_RECENCY = 0.30
WEIGHT_LINK_DENSITY = 0.25
WEIGHT_COMPLETION_STATE = 0.20
WEIGHT_REFERENCE_FREQUENCY = 0.15
WEIGHT_USER_INTERACTION = 0.10

# Decay half-life in days for recency scoring
RECENCY_HALF_LIFE_DAYS = 14.0
INTERACTION_HALF_LIFE_DAYS = 7.0

# Max edge count for normalization (nodes with more edges still get 1.0)
MAX_EDGE_COUNT = 20


def _compute_recency_score(updated_at: datetime, now: datetime) -> float:
    """
    Exponential decay based on days since last update.
    Score = e^(-lambda * days) where lambda = ln(2) / half_life
    Invariant D-02: Recomputable from node.updated_at.
    """
    delta = (now - updated_at).total_seconds() / 86400.0  # days
    if delta <= 0:
        return 1.0
    decay_rate = math.log(2) / RECENCY_HALF_LIFE_DAYS
    return max(0.0, min(1.0, math.exp(-decay_rate * delta)))


def _compute_link_density_score(total_edges: int) -> float:
    """
    Normalized edge count. More connections = higher score.
    Invariant D-02: Recomputable from edges table.
    """
    if total_edges <= 0:
        return 0.0
    return min(1.0, total_edges / MAX_EDGE_COUNT)


def _compute_completion_state_score(
    node_type: NodeType,
    task_status: TaskStatus | None = None,
    goal_status: GoalStatus | None = None,
    goal_progress: float | None = None,
) -> float:
    """
    Completion-based scoring:
    - Tasks: done=1.0, in_progress=0.7, todo=0.3, cancelled=0.1
    - Goals: active with progress, completed=1.0
    - Other types: neutral 0.5
    Invariant D-02: Recomputable from task_nodes/goal_nodes status.
    """
    if node_type == NodeType.TASK and task_status:
        return {
            TaskStatus.DONE: 1.0,
            TaskStatus.IN_PROGRESS: 0.7,
            TaskStatus.TODO: 0.3,
            TaskStatus.CANCELLED: 0.1,
        }.get(task_status, 0.5)

    if node_type == NodeType.GOAL and goal_status:
        if goal_status == GoalStatus.COMPLETED:
            return 1.0
        if goal_status == GoalStatus.ARCHIVED:
            return 0.2
        # Active: scale by progress
        return 0.3 + 0.7 * (goal_progress or 0.0)

    # Non-task, non-goal types get neutral score
    return 0.5


def _compute_reference_frequency_score(incoming_edges: int) -> float:
    """
    How often other nodes reference this one (incoming edges).
    Invariant D-02: Recomputable from edges table.
    """
    if incoming_edges <= 0:
        return 0.0
    return min(1.0, incoming_edges / 10.0)


def _compute_user_interaction_score(
    last_accessed_at: datetime | None,
    now: datetime,
) -> float:
    """
    Exponential decay based on last user interaction.
    Invariant D-02: Recomputable from node.last_accessed_at (BEHAVIORAL TRACKING, S-01).
    """
    if last_accessed_at is None:
        return 0.0
    delta = (now - last_accessed_at).total_seconds() / 86400.0
    if delta <= 0:
        return 1.0
    decay_rate = math.log(2) / INTERACTION_HALF_LIFE_DAYS
    return max(0.0, min(1.0, math.exp(-decay_rate * delta)))


async def compute_signal_score(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> SignalScore | None:
    """
    Compute and persist the signal score for a single node.

    Invariant D-02: All factors are recomputed from Core + Temporal data.
    Invariant D-03: Result stored in signal_scores (non-canonical).
    """
    # Fetch node with ownership check
    stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    if node is None:
        return None

    now = datetime.now(timezone.utc)

    # Factor 1: Recency (weight 0.3)
    recency = _compute_recency_score(
        node.updated_at.replace(tzinfo=timezone.utc) if node.updated_at.tzinfo is None else node.updated_at,
        now,
    )

    # Factor 2: Link density (weight 0.25) — count active edges
    edge_count_stmt = select(func.count()).select_from(Edge).where(
        or_(Edge.source_id == node_id, Edge.target_id == node_id),
        Edge.state == EdgeState.ACTIVE,
    )
    total_edges = (await db.execute(edge_count_stmt)).scalar_one()
    link_density = _compute_link_density_score(total_edges)

    # Factor 3: Completion state (weight 0.2) — depends on node type
    task_status = None
    goal_status = None
    goal_progress = None

    if node.type == NodeType.TASK:
        task_result = await db.execute(
            select(TaskNode).where(TaskNode.node_id == node_id)
        )
        task = task_result.scalar_one_or_none()
        if task:
            task_status = task.status

    elif node.type == NodeType.GOAL:
        goal_result = await db.execute(
            select(GoalNode).where(GoalNode.node_id == node_id)
        )
        goal = goal_result.scalar_one_or_none()
        if goal:
            goal_status = goal.status
            goal_progress = goal.progress

    completion = _compute_completion_state_score(
        node.type, task_status, goal_status, goal_progress
    )

    # Factor 4: Reference frequency (weight 0.15) — incoming edges only
    incoming_stmt = select(func.count()).select_from(Edge).where(
        Edge.target_id == node_id,
        Edge.state == EdgeState.ACTIVE,
    )
    incoming_edges = (await db.execute(incoming_stmt)).scalar_one()
    reference_freq = _compute_reference_frequency_score(incoming_edges)

    # Factor 5: User interaction (weight 0.1)
    accessed_at = node.last_accessed_at
    if accessed_at and accessed_at.tzinfo is None:
        accessed_at = accessed_at.replace(tzinfo=timezone.utc)
    interaction = _compute_user_interaction_score(accessed_at, now)

    # Composite score
    composite = (
        WEIGHT_RECENCY * recency
        + WEIGHT_LINK_DENSITY * link_density
        + WEIGHT_COMPLETION_STATE * completion
        + WEIGHT_REFERENCE_FREQUENCY * reference_freq
        + WEIGHT_USER_INTERACTION * interaction
    )
    composite = max(0.0, min(1.0, composite))

    # Upsert into signal_scores table (Invariant D-03: non-canonical storage)
    existing = await db.execute(
        select(SignalScore).where(SignalScore.node_id == node_id)
    )
    signal = existing.scalar_one_or_none()

    if signal is None:
        signal = SignalScore(
            node_id=node_id,
            score=composite,
            recency_score=recency,
            link_density_score=link_density,
            completion_state_score=completion,
            reference_frequency_score=reference_freq,
            user_interaction_score=interaction,
            computed_at=now,
        )
        db.add(signal)
    else:
        signal.score = composite
        signal.recency_score = recency
        signal.link_density_score = link_density
        signal.completion_state_score = completion
        signal.reference_frequency_score = reference_freq
        signal.user_interaction_score = interaction
        signal.computed_at = now

    await db.flush()
    return signal


async def compute_signal_scores_batch(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_ids: list[uuid.UUID] | None = None,
    limit: int = 100,
) -> list[SignalScore]:
    """
    Batch compute signal scores for multiple nodes.
    If node_ids is None, computes for all non-archived nodes.

    Invariant D-02: All results are recomputable.
    """
    if node_ids:
        ids_to_process = node_ids
    else:
        stmt = (
            select(Node.id)
            .where(Node.owner_id == owner_id, Node.archived_at.is_(None))
            .order_by(Node.updated_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        ids_to_process = [row[0] for row in result.all()]

    scores = []
    for nid in ids_to_process:
        score = await compute_signal_score(db, owner_id, nid)
        if score:
            scores.append(score)

    return scores


async def get_signal_score(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> SignalScore | None:
    """Get the cached signal score for a node."""
    result = await db.execute(
        select(SignalScore).where(SignalScore.node_id == node_id)
    )
    return result.scalar_one_or_none()


async def get_signal_scores_for_nodes(
    db: AsyncSession,
    node_ids: list[uuid.UUID],
) -> dict[uuid.UUID, SignalScore]:
    """Get cached signal scores for multiple nodes."""
    if not node_ids:
        return {}
    stmt = select(SignalScore).where(SignalScore.node_id.in_(node_ids))
    result = await db.execute(stmt)
    scores = result.scalars().all()
    return {s.node_id: s for s in scores}
