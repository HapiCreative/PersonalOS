"""
Monthly review behavioral workflow (Section 5.5).
Same pattern as weekly, scoped to strategic questions.
References the month's weekly snapshots. Produces monthly_snapshots record.

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-04: Ownership alignment on all operations.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from dataclasses import dataclass, field
import calendar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, GoalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, GoalStatus, EdgeRelationType, EdgeState,
    TaskExecutionEventType,
)
from server.app.temporal.models import (
    TaskExecutionEvent, WeeklySnapshot, MonthlySnapshot, FocusSession,
)


@dataclass
class MonthlyGoalSummary:
    """Summary of a goal's progress over the month."""
    node_id: uuid.UUID
    title: str
    status: str
    progress: float
    tasks_completed_this_month: int


@dataclass
class WeeklySnapshotSummary:
    """Summary of a weekly snapshot for the monthly view."""
    week_start: date
    week_end: date
    focus_areas: list[str]
    notes: str | None


@dataclass
class MonthlyReviewSummary:
    """System-generated summary for the monthly review."""
    month: date  # First day of month
    month_name: str
    weekly_snapshots: list[WeeklySnapshotSummary]
    goals: list[MonthlyGoalSummary]
    total_tasks_completed: int
    total_focus_time_seconds: int
    existing_snapshot: dict | None = None


def _get_month_bounds(reference_date: date | None = None) -> tuple[date, date]:
    """Get first and last day of the month containing reference_date."""
    ref = reference_date or date.today()
    first_day = ref.replace(day=1)
    last_day = ref.replace(day=calendar.monthrange(ref.year, ref.month)[1])
    return first_day, last_day


async def get_monthly_review_summary(
    db: AsyncSession,
    owner_id: uuid.UUID,
    reference_date: date | None = None,
) -> MonthlyReviewSummary:
    """
    Generate the monthly review summary.
    References the month's weekly snapshots (via Core user_id, not temporal FK).
    """
    month_start, month_end = _get_month_bounds(reference_date)
    month_label = month_start.strftime("%B %Y")

    # Check for existing snapshot
    existing_stmt = select(MonthlySnapshot).where(
        MonthlySnapshot.user_id == owner_id,
        MonthlySnapshot.month == month_start,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()
    existing_dict = None
    if existing:
        existing_dict = {
            "id": str(existing.id),
            "month": existing.month.isoformat(),
            "focus_areas": existing.focus_areas,
            "notes": existing.notes,
            "created_at": existing.created_at.isoformat(),
        }

    # Get weekly snapshots for this month
    # Invariant T-01: Joins through user_id (Core), not through temporal tables
    weekly_stmt = (
        select(WeeklySnapshot)
        .where(
            WeeklySnapshot.user_id == owner_id,
            WeeklySnapshot.week_start_date >= month_start,
            WeeklySnapshot.week_start_date <= month_end,
        )
        .order_by(WeeklySnapshot.week_start_date.asc())
    )
    weekly_result = await db.execute(weekly_stmt)
    weeklies = list(weekly_result.scalars().all())

    weekly_summaries = [
        WeeklySnapshotSummary(
            week_start=w.week_start_date,
            week_end=w.week_end_date,
            focus_areas=w.focus_areas,
            notes=w.notes,
        )
        for w in weeklies
    ]

    # Get active goals
    goals_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.status.in_([GoalStatus.ACTIVE, GoalStatus.COMPLETED]),
        )
        .order_by(GoalNode.progress.desc())
    )
    goals_result = await db.execute(goals_stmt)
    goal_rows = list(goals_result.all())

    goal_summaries = []
    for node, goal in goal_rows:
        # Count tasks completed this month for this goal
        completed_stmt = (
            select(func.count())
            .select_from(TaskExecutionEvent)
            .join(Edge, Edge.target_id == TaskExecutionEvent.task_id)
            .where(
                Edge.source_id == node.id,
                Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
                Edge.state == EdgeState.ACTIVE,
                TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
                TaskExecutionEvent.expected_for_date >= month_start,
                TaskExecutionEvent.expected_for_date <= month_end,
                TaskExecutionEvent.node_deleted == False,
            )
        )
        tasks_completed = (await db.execute(completed_stmt)).scalar_one()

        goal_summaries.append(MonthlyGoalSummary(
            node_id=node.id,
            title=node.title,
            status=goal.status.value,
            progress=goal.progress,
            tasks_completed_this_month=tasks_completed,
        ))

    # Total tasks completed this month
    total_completed_stmt = (
        select(func.count())
        .select_from(TaskExecutionEvent)
        .where(
            TaskExecutionEvent.user_id == owner_id,
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.expected_for_date >= month_start,
            TaskExecutionEvent.expected_for_date <= month_end,
            TaskExecutionEvent.node_deleted == False,
        )
    )
    total_completed = (await db.execute(total_completed_stmt)).scalar_one()

    # Total focus time this month
    focus_stmt = select(func.coalesce(func.sum(FocusSession.duration), 0)).where(
        FocusSession.user_id == owner_id,
        FocusSession.started_at >= datetime.combine(month_start, datetime.min.time()).replace(tzinfo=timezone.utc),
        FocusSession.started_at <= datetime.combine(month_end, datetime.max.time()).replace(tzinfo=timezone.utc),
        FocusSession.duration.isnot(None),
    )
    total_focus = (await db.execute(focus_stmt)).scalar_one()

    return MonthlyReviewSummary(
        month=month_start,
        month_name=month_label,
        weekly_snapshots=weekly_summaries,
        goals=goal_summaries,
        total_tasks_completed=total_completed,
        total_focus_time_seconds=total_focus,
        existing_snapshot=existing_dict,
    )


async def save_monthly_snapshot(
    db: AsyncSession,
    owner_id: uuid.UUID,
    focus_areas: list[str],
    notes: str | None = None,
    reference_date: date | None = None,
) -> MonthlySnapshot:
    """
    Save the monthly review as a monthly_snapshots record.
    Creates or updates (first commit wins, updates in place).
    Invariant T-04: Ownership alignment.
    """
    month_start, _ = _get_month_bounds(reference_date)

    # Check for existing snapshot
    stmt = select(MonthlySnapshot).where(
        MonthlySnapshot.user_id == owner_id,
        MonthlySnapshot.month == month_start,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.focus_areas = focus_areas
        existing.notes = notes
        await db.flush()
        return existing

    snapshot = MonthlySnapshot(
        user_id=owner_id,
        month=month_start,
        focus_areas=focus_areas,
        notes=notes,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot
