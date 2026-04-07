"""
Morning commit behavioral workflow (Section 5.1).
Commit stage of the 4-stage daily cycle: commit -> execute -> reflect -> learn.

Workflow:
1. System suggests tasks based on signal score, due dates, goal drift
2. User selects 1-3 priorities + optional secondary tasks
3. User sets intention (optional)
4. Produces daily_plans record (Temporal)

Invariant T-04: Ownership alignment on all operations.
Invariant U-04: Focus section cap 1-3 tasks.
"""

import uuid
from datetime import date, datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode, GoalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, TaskStatus, TaskPriority, GoalStatus,
    EdgeRelationType, EdgeState,
)
from server.app.derived.signal_score import get_signal_scores_for_nodes
from server.app.temporal.daily_plans_service import create_daily_plan, get_daily_plan


@dataclass
class SuggestedTask:
    """A task suggested by the system for morning commit."""
    node_id: uuid.UUID
    title: str
    priority: str
    due_date: date | None
    status: str
    is_recurring: bool
    signal_score: float | None
    reason: str  # Why it's suggested (due_today, overdue, high_signal, goal_drift)
    goal_title: str | None = None  # If linked to a goal


@dataclass
class MorningCommitSuggestions:
    """System-generated suggestions for the morning commit."""
    suggested_tasks: list[SuggestedTask]
    existing_plan: dict | None  # If plan already exists for today
    date: date
    ai_briefing: list[str]  # 3-5 bullet points (stub, full AI in P9)


async def _get_overdue_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    today: date,
) -> list[SuggestedTask]:
    """Get overdue tasks (highest priority for suggestion)."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            TaskNode.due_date.isnot(None),
            TaskNode.due_date < today,
        )
        .order_by(TaskNode.priority.desc(), TaskNode.due_date.asc())
        .limit(5)
    )
    result = await db.execute(stmt)
    rows = list(result.all())
    return [
        SuggestedTask(
            node_id=node.id,
            title=node.title,
            priority=task.priority.value,
            due_date=task.due_date,
            status=task.status.value,
            is_recurring=task.is_recurring,
            signal_score=None,
            reason="overdue",
        )
        for node, task in rows
    ]


async def _get_due_today_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    today: date,
) -> list[SuggestedTask]:
    """Get tasks due today."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
            TaskNode.due_date == today,
        )
        .order_by(TaskNode.priority.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    rows = list(result.all())
    return [
        SuggestedTask(
            node_id=node.id,
            title=node.title,
            priority=task.priority.value,
            due_date=task.due_date,
            status=task.status.value,
            is_recurring=task.is_recurring,
            signal_score=None,
            reason="due_today",
        )
        for node, task in rows
    ]


async def _get_high_signal_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    exclude_ids: set[uuid.UUID],
) -> list[SuggestedTask]:
    """Get high-signal open tasks (by signal score)."""
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
        )
        .order_by(TaskNode.priority.desc(), Node.updated_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    # Filter out already-suggested tasks
    filtered = [(n, t) for n, t in rows if n.id not in exclude_ids]

    # Get signal scores for these tasks
    node_ids = [n.id for n, _ in filtered]
    scores = await get_signal_scores_for_nodes(db, node_ids) if node_ids else {}

    suggestions = []
    for node, task in filtered[:5]:
        score = scores.get(node.id)
        suggestions.append(SuggestedTask(
            node_id=node.id,
            title=node.title,
            priority=task.priority.value,
            due_date=task.due_date,
            status=task.status.value,
            is_recurring=task.is_recurring,
            signal_score=score.score if score else None,
            reason="high_signal",
        ))
    return suggestions


async def _get_goal_drift_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    exclude_ids: set[uuid.UUID],
) -> list[SuggestedTask]:
    """
    Get tasks linked to active goals with low progress (goal drift).
    These are tasks that would advance stalling goals.
    """
    # Find active goals with low progress
    goal_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.status == GoalStatus.ACTIVE,
            GoalNode.progress < 0.3,  # Goals with less than 30% progress
        )
        .order_by(GoalNode.progress.asc())
        .limit(3)
    )
    goal_result = await db.execute(goal_stmt)
    goal_rows = list(goal_result.all())

    suggestions = []
    for goal_node, goal in goal_rows:
        # Find open tasks linked to this goal
        task_stmt = (
            select(Node, TaskNode)
            .join(TaskNode, TaskNode.node_id == Node.id)
            .join(Edge, Edge.target_id == Node.id)
            .where(
                Edge.source_id == goal_node.id,
                Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
                Edge.state == EdgeState.ACTIVE,
                Node.owner_id == owner_id,
                Node.archived_at.is_(None),
                TaskNode.status.in_([TaskStatus.TODO, TaskStatus.IN_PROGRESS]),
                Node.id.notin_(exclude_ids) if exclude_ids else True,
            )
            .order_by(TaskNode.priority.desc())
            .limit(2)
        )
        task_result = await db.execute(task_stmt)
        task_rows = list(task_result.all())

        for node, task in task_rows:
            if node.id not in exclude_ids:
                suggestions.append(SuggestedTask(
                    node_id=node.id,
                    title=node.title,
                    priority=task.priority.value,
                    due_date=task.due_date,
                    status=task.status.value,
                    is_recurring=task.is_recurring,
                    signal_score=None,
                    reason="goal_drift",
                    goal_title=goal_node.title,
                ))

    return suggestions[:3]


def _generate_ai_briefing_stub(
    suggestions: list[SuggestedTask],
    today: date,
) -> list[str]:
    """
    Generate AI briefing stub (3-5 bullets).
    Full AI integration comes in Phase 9.
    """
    bullets = []

    overdue = [s for s in suggestions if s.reason == "overdue"]
    due_today = [s for s in suggestions if s.reason == "due_today"]
    drift = [s for s in suggestions if s.reason == "goal_drift"]

    if overdue:
        bullets.append(f"You have {len(overdue)} overdue task{'s' if len(overdue) > 1 else ''} that need attention.")

    if due_today:
        bullets.append(f"{len(due_today)} task{'s are' if len(due_today) > 1 else ' is'} due today.")

    if drift:
        goal_names = list({s.goal_title for s in drift if s.goal_title})
        if goal_names:
            bullets.append(f"Goals needing progress: {', '.join(goal_names[:2])}.")

    if not bullets:
        bullets.append("No urgent items today. A good day to make progress on your priorities.")

    bullets.append(f"Today is {today.strftime('%A, %B %d')}. Set your intention and commit to your plan.")

    return bullets[:5]


async def get_morning_suggestions(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> MorningCommitSuggestions:
    """
    Generate morning commit suggestions.
    Aggregates tasks by: overdue, due today, high signal, goal drift.
    """
    today = date.today()

    # Check for existing plan
    existing_plan = await get_daily_plan(db, owner_id, today)
    existing_dict = None
    if existing_plan:
        existing_dict = {
            "id": str(existing_plan.id),
            "date": existing_plan.date.isoformat(),
            "selected_task_ids": [str(tid) for tid in existing_plan.selected_task_ids],
            "intention_text": existing_plan.intention_text,
            "closed_at": existing_plan.closed_at.isoformat() if existing_plan.closed_at else None,
        }

    # Gather suggestions in priority order
    overdue = await _get_overdue_tasks(db, owner_id, today)
    due_today = await _get_due_today_tasks(db, owner_id, today)

    seen_ids = {s.node_id for s in overdue + due_today}
    high_signal = await _get_high_signal_tasks(db, owner_id, seen_ids)

    seen_ids.update(s.node_id for s in high_signal)
    goal_drift = await _get_goal_drift_tasks(db, owner_id, seen_ids)

    # Combine and deduplicate
    all_suggestions = overdue + due_today + high_signal + goal_drift
    seen = set()
    deduped = []
    for s in all_suggestions:
        if s.node_id not in seen:
            seen.add(s.node_id)
            deduped.append(s)

    # Phase 9: Generate AI briefing (full AI integration)
    try:
        from server.app.behavioral.ai_modes import generate_briefing
        briefing = await generate_briefing(db, owner_id)
    except Exception:
        # Fallback to heuristic briefing if AI fails
        briefing = _generate_ai_briefing_stub(deduped, today)

    return MorningCommitSuggestions(
        suggested_tasks=deduped,
        existing_plan=existing_dict,
        date=today,
        ai_briefing=briefing,
    )


async def commit_morning_plan(
    db: AsyncSession,
    owner_id: uuid.UUID,
    selected_task_ids: list[uuid.UUID],
    intention_text: str | None = None,
) -> dict:
    """
    Commit the morning plan: create or update daily_plans record.
    Invariant U-04: Focus section allows 1-3 primary tasks.

    Returns the created/updated plan as a dict.
    """
    today = date.today()

    # Create or update the daily plan
    plan = await create_daily_plan(
        db, owner_id, today, selected_task_ids, intention_text,
    )

    return {
        "id": str(plan.id),
        "date": plan.date.isoformat(),
        "selected_task_ids": [str(tid) for tid in plan.selected_task_ids],
        "intention_text": plan.intention_text,
        "created_at": plan.created_at.isoformat(),
        "closed_at": plan.closed_at.isoformat() if plan.closed_at else None,
    }
