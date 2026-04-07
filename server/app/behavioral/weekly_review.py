"""
Weekly review behavioral workflow (Section 5.5).
Hybrid summary + guided workflow → weekly_snapshots.

Workflow:
1. System generates derived summary: completed vs planned, patterns, stalled items
2. Guided workflow: review → evaluate goals → adjust priorities → set next week focus
3. Output: weekly_snapshots record (Temporal)

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-04: Ownership alignment on all operations.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from dataclasses import dataclass, field

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode, GoalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, TaskStatus, GoalStatus, EdgeRelationType, EdgeState,
)
from server.app.temporal.models import (
    DailyPlan, TaskExecutionEvent, WeeklySnapshot,
)
from server.app.core.models.enums import TaskExecutionEventType


@dataclass
class WeeklyTaskSummary:
    """Summary of a task's activity during the week."""
    node_id: uuid.UUID
    title: str
    status: str
    priority: str
    completed: bool
    was_planned: bool  # Was in any daily plan this week


@dataclass
class WeeklyGoalSummary:
    """Summary of a goal's state during the week."""
    node_id: uuid.UUID
    title: str
    status: str
    progress: float
    linked_task_count: int
    completed_task_count: int


@dataclass
class WeeklyReviewSummary:
    """System-generated summary for the weekly review."""
    week_start: date
    week_end: date
    completed_tasks: list[WeeklyTaskSummary]
    planned_tasks: list[WeeklyTaskSummary]
    stalled_goals: list[WeeklyGoalSummary]
    active_goals: list[WeeklyGoalSummary]
    total_planned: int
    total_completed: int
    completion_rate: float
    total_focus_time_seconds: int
    existing_snapshot: dict | None = None


def _get_week_bounds(reference_date: date | None = None) -> tuple[date, date]:
    """Get Monday-Sunday bounds for the week containing reference_date."""
    ref = reference_date or date.today()
    # Monday = 0
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


async def get_weekly_review_summary(
    db: AsyncSession,
    owner_id: uuid.UUID,
    reference_date: date | None = None,
) -> WeeklyReviewSummary:
    """
    Generate the weekly review summary.
    Looks at the week containing reference_date (defaults to current week).
    """
    week_start, week_end = _get_week_bounds(reference_date)

    # Check for existing snapshot
    existing_stmt = select(WeeklySnapshot).where(
        WeeklySnapshot.user_id == owner_id,
        WeeklySnapshot.week_start_date == week_start,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()
    existing_dict = None
    if existing:
        existing_dict = {
            "id": str(existing.id),
            "week_start_date": existing.week_start_date.isoformat(),
            "week_end_date": existing.week_end_date.isoformat(),
            "focus_areas": existing.focus_areas,
            "priority_task_ids": [str(tid) for tid in (existing.priority_task_ids or [])],
            "notes": existing.notes,
            "created_at": existing.created_at.isoformat(),
        }

    # Get completed tasks this week (via execution events)
    completed_stmt = (
        select(Node, TaskNode, TaskExecutionEvent)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .join(TaskExecutionEvent, TaskExecutionEvent.task_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.expected_for_date >= week_start,
            TaskExecutionEvent.expected_for_date <= week_end,
            TaskExecutionEvent.node_deleted == False,
        )
        .order_by(TaskExecutionEvent.expected_for_date.asc())
    )
    completed_result = await db.execute(completed_stmt)
    completed_rows = list(completed_result.all())

    # Get tasks that appeared in daily plans this week
    plans_stmt = select(DailyPlan).where(
        DailyPlan.user_id == owner_id,
        DailyPlan.date >= week_start,
        DailyPlan.date <= week_end,
    )
    plans_result = await db.execute(plans_stmt)
    plans = list(plans_result.scalars().all())

    planned_task_ids: set[uuid.UUID] = set()
    for plan in plans:
        planned_task_ids.update(plan.selected_task_ids)

    # Build completed task summaries
    completed_tasks = []
    completed_ids: set[uuid.UUID] = set()
    for node, task, event in completed_rows:
        if node.id not in completed_ids:
            completed_ids.add(node.id)
            completed_tasks.append(WeeklyTaskSummary(
                node_id=node.id,
                title=node.title,
                status=task.status.value,
                priority=task.priority.value,
                completed=True,
                was_planned=node.id in planned_task_ids,
            ))

    # Build planned task summaries for tasks not completed
    planned_tasks = []
    if planned_task_ids:
        planned_stmt = (
            select(Node, TaskNode)
            .join(TaskNode, TaskNode.node_id == Node.id)
            .where(
                Node.id.in_(planned_task_ids - completed_ids),
                Node.owner_id == owner_id,
            )
        )
        planned_result = await db.execute(planned_stmt)
        for node, task in planned_result.all():
            planned_tasks.append(WeeklyTaskSummary(
                node_id=node.id,
                title=node.title,
                status=task.status.value,
                priority=task.priority.value,
                completed=False,
                was_planned=True,
            ))

    # Get active goals with progress info
    goals_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.status == GoalStatus.ACTIVE,
        )
        .order_by(GoalNode.progress.asc())
    )
    goals_result = await db.execute(goals_stmt)
    goal_rows = list(goals_result.all())

    active_goals = []
    stalled_goals = []
    for node, goal in goal_rows:
        # Count linked tasks
        link_count_stmt = select(func.count()).select_from(Edge).where(
            Edge.source_id == node.id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
        )
        link_count = (await db.execute(link_count_stmt)).scalar_one()

        # Count completed linked tasks this week
        completed_link_stmt = (
            select(func.count())
            .select_from(TaskExecutionEvent)
            .join(Edge, Edge.target_id == TaskExecutionEvent.task_id)
            .where(
                Edge.source_id == node.id,
                Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
                Edge.state == EdgeState.ACTIVE,
                TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
                TaskExecutionEvent.expected_for_date >= week_start,
                TaskExecutionEvent.expected_for_date <= week_end,
                TaskExecutionEvent.node_deleted == False,
            )
        )
        completed_link_count = (await db.execute(completed_link_stmt)).scalar_one()

        summary = WeeklyGoalSummary(
            node_id=node.id,
            title=node.title,
            status=goal.status.value,
            progress=goal.progress,
            linked_task_count=link_count,
            completed_task_count=completed_link_count,
        )

        if goal.progress < 0.3 and completed_link_count == 0:
            stalled_goals.append(summary)
        active_goals.append(summary)

    # Compute total focus time for the week
    from server.app.temporal.models import FocusSession
    focus_stmt = select(func.coalesce(func.sum(FocusSession.duration), 0)).where(
        FocusSession.user_id == owner_id,
        FocusSession.started_at >= datetime.combine(week_start, datetime.min.time()).replace(tzinfo=timezone.utc),
        FocusSession.started_at <= datetime.combine(week_end, datetime.max.time()).replace(tzinfo=timezone.utc),
        FocusSession.duration.isnot(None),
    )
    total_focus = (await db.execute(focus_stmt)).scalar_one()

    total_planned = len(planned_task_ids)
    total_completed = len(completed_ids)
    completion_rate = total_completed / total_planned if total_planned > 0 else 0.0

    return WeeklyReviewSummary(
        week_start=week_start,
        week_end=week_end,
        completed_tasks=completed_tasks,
        planned_tasks=planned_tasks,
        stalled_goals=stalled_goals,
        active_goals=active_goals,
        total_planned=total_planned,
        total_completed=total_completed,
        completion_rate=min(completion_rate, 1.0),
        total_focus_time_seconds=total_focus,
        existing_snapshot=existing_dict,
    )


async def save_weekly_snapshot(
    db: AsyncSession,
    owner_id: uuid.UUID,
    focus_areas: list[str],
    priority_task_ids: list[uuid.UUID] | None = None,
    notes: str | None = None,
    reference_date: date | None = None,
) -> WeeklySnapshot:
    """
    Save the weekly review as a weekly_snapshots record.
    Creates or updates (first commit wins, updates in place).
    Invariant T-04: Ownership alignment.
    """
    week_start, week_end = _get_week_bounds(reference_date)

    # Check for existing snapshot
    stmt = select(WeeklySnapshot).where(
        WeeklySnapshot.user_id == owner_id,
        WeeklySnapshot.week_start_date == week_start,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update in place
        existing.focus_areas = focus_areas
        existing.priority_task_ids = priority_task_ids
        existing.notes = notes
        await db.flush()
        return existing

    snapshot = WeeklySnapshot(
        user_id=owner_id,
        week_start_date=week_start,
        week_end_date=week_end,
        focus_areas=focus_areas,
        priority_task_ids=priority_task_ids,
        notes=notes,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot
