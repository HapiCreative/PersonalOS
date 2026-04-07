"""
Analytics rollup computation service (Section 4.7 — Derived Layer).

Two-tier analytics model:
- Tier A (operational): today/7d/14d — live query from Core + Temporal data.
- Tier B (trend): 30d/90d/6mo/1y — pre-aggregated rollup tables.

Rollup tables are Derived, not Temporal. Temporal = what happened. Derived = what it means.

Invariant D-02: Fully recomputable from Core + Temporal data.
Invariant D-03: Non-canonical storage.
Invariant D-04: Analytics output classification (descriptive/correlational/recommendation).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import delete, func, select, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, GoalNode, JournalNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, GoalStatus, EdgeRelationType, EdgeState,
    TaskExecutionEventType, Mood,
)
from server.app.temporal.models import (
    TaskExecutionEvent, DailyPlan, FocusSession,
)
from server.app.derived.models import (
    AnalyticsDailyRollup, AnalyticsWeeklyRollup, ProgressIntelligence,
)
from server.app.derived.schemas import DerivedExplanation, DerivedFactor


# =============================================================================
# Invariant D-04: Analytics output classification
# =============================================================================

# Analytics outputs must be classified as one of three tiers:
#   - descriptive: raw facts (no label in UI)
#   - correlational: "Pattern detected" — both variables shown, never implies causation
#   - recommendation: "Suggestion" — cites underlying correlation, dismissible
AnalyticsClassification = Literal["descriptive", "correlational", "recommendation"]


@dataclass
class AnalyticsOutput:
    """
    Invariant D-04: Every analytics output must have an explicit classification.
    Invariant D-01: User-facing outputs include DerivedExplanation.
    """
    classification: AnalyticsClassification
    label: str  # "Pattern detected" for correlational, "Suggestion" for recommendation, "" for descriptive
    explanation: DerivedExplanation
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "classification": self.classification,
            "label": self.label,
            "explanation": self.explanation.to_dict(),
            "data": self.data,
        }


MOOD_SCORE_MAP = {
    Mood.GREAT: 5.0,
    Mood.GOOD: 4.0,
    Mood.NEUTRAL: 3.0,
    Mood.LOW: 2.0,
    Mood.BAD: 1.0,
}


# =============================================================================
# Tier A: Live queries (today/7d/14d)
# =============================================================================


@dataclass
class TierAMetrics:
    """Tier A operational metrics computed from live queries."""
    period: str  # "today", "7d", "14d"
    start_date: date
    end_date: date

    # Task metrics
    tasks_completed: int = 0
    tasks_planned: int = 0
    tasks_planned_completed: int = 0
    planning_accuracy: float = 0.0

    # Focus metrics
    focus_seconds_total: int = 0
    focus_sessions_count: int = 0

    # Journal metrics
    journal_entries: int = 0
    avg_mood: float | None = None
    mood_values: list[float] = field(default_factory=list)

    # Streak
    current_streak: int = 0


async def compute_tier_a_metrics(
    db: AsyncSession,
    user_id: uuid.UUID,
    period: str = "7d",
) -> TierAMetrics:
    """
    Tier A: Live query metrics for operational analytics.
    Invariant D-02: Computed directly from Core + Temporal data.
    """
    now = date.today()
    if period == "today":
        start = now
    elif period == "7d":
        start = now - timedelta(days=7)
    elif period == "14d":
        start = now - timedelta(days=14)
    else:
        start = now - timedelta(days=7)

    metrics = TierAMetrics(period=period, start_date=start, end_date=now)

    # Tasks completed (from task_execution_events)
    completed_stmt = select(func.count()).select_from(TaskExecutionEvent).where(
        TaskExecutionEvent.user_id == user_id,
        TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
        TaskExecutionEvent.expected_for_date >= start,
        TaskExecutionEvent.expected_for_date <= now,
        TaskExecutionEvent.node_deleted.is_(False),
    )
    result = await db.execute(completed_stmt)
    metrics.tasks_completed = result.scalar() or 0

    # Tasks planned (from daily_plans)
    plans_stmt = select(DailyPlan).where(
        DailyPlan.user_id == user_id,
        DailyPlan.date >= start,
        DailyPlan.date <= now,
    )
    result = await db.execute(plans_stmt)
    plans = list(result.scalars().all())

    all_planned_ids = set()
    for plan in plans:
        if plan.selected_task_ids:
            all_planned_ids.update(plan.selected_task_ids)
    metrics.tasks_planned = len(all_planned_ids)

    # Tasks planned AND completed
    if all_planned_ids:
        planned_completed_stmt = select(func.count(func.distinct(TaskExecutionEvent.task_id))).where(
            TaskExecutionEvent.user_id == user_id,
            TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
            TaskExecutionEvent.expected_for_date >= start,
            TaskExecutionEvent.expected_for_date <= now,
            TaskExecutionEvent.task_id.in_(all_planned_ids),
            TaskExecutionEvent.node_deleted.is_(False),
        )
        result = await db.execute(planned_completed_stmt)
        metrics.tasks_planned_completed = result.scalar() or 0

    if metrics.tasks_planned > 0:
        metrics.planning_accuracy = metrics.tasks_planned_completed / metrics.tasks_planned

    # Focus sessions
    focus_stmt = select(
        func.count(),
        func.coalesce(func.sum(FocusSession.duration), 0),
    ).where(
        FocusSession.user_id == user_id,
        cast(FocusSession.started_at, Date) >= start,
        cast(FocusSession.started_at, Date) <= now,
        FocusSession.ended_at.isnot(None),
    )
    result = await db.execute(focus_stmt)
    row = result.one()
    metrics.focus_sessions_count = row[0] or 0
    metrics.focus_seconds_total = row[1] or 0

    # Journal entries + mood
    journal_stmt = select(JournalNode.mood).where(
        JournalNode.node_id.in_(
            select(Node.id).where(
                Node.owner_id == user_id,
                Node.type == NodeType.JOURNAL_ENTRY,
                Node.archived_at.is_(None),
            )
        ),
        JournalNode.entry_date >= start,
        JournalNode.entry_date <= now,
    )
    result = await db.execute(journal_stmt)
    moods = [r[0] for r in result.all() if r[0] is not None]
    metrics.journal_entries = len(moods)
    if moods:
        scores = [MOOD_SCORE_MAP.get(m, 3.0) for m in moods]
        metrics.mood_values = scores
        metrics.avg_mood = sum(scores) / len(scores)

    # Compute streak (consecutive days with completed tasks, backwards from today)
    streak = 0
    check_date = now
    while True:
        has_completion = await db.execute(
            select(func.count()).select_from(TaskExecutionEvent).where(
                TaskExecutionEvent.user_id == user_id,
                TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
                TaskExecutionEvent.expected_for_date == check_date,
                TaskExecutionEvent.node_deleted.is_(False),
            )
        )
        if (has_completion.scalar() or 0) > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    metrics.current_streak = streak

    return metrics


# =============================================================================
# Tier B: Pre-aggregated rollup computation
# =============================================================================


async def compute_daily_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: date,
) -> AnalyticsDailyRollup:
    """
    Compute and persist a daily rollup for a specific date.
    Invariant D-02: Fully recomputable from Core + Temporal data.
    """
    # Tasks completed
    completed_stmt = select(func.count()).select_from(TaskExecutionEvent).where(
        TaskExecutionEvent.user_id == user_id,
        TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
        TaskExecutionEvent.expected_for_date == target_date,
        TaskExecutionEvent.node_deleted.is_(False),
    )
    result = await db.execute(completed_stmt)
    tasks_completed = result.scalar() or 0

    # Get completed task IDs for cross-referencing
    completed_task_ids_stmt = select(TaskExecutionEvent.task_id).where(
        TaskExecutionEvent.user_id == user_id,
        TaskExecutionEvent.event_type == TaskExecutionEventType.COMPLETED,
        TaskExecutionEvent.expected_for_date == target_date,
        TaskExecutionEvent.node_deleted.is_(False),
    )
    result = await db.execute(completed_task_ids_stmt)
    completed_task_ids = set(r[0] for r in result.all())

    # Tasks planned (from daily_plans)
    plan_stmt = select(DailyPlan).where(
        DailyPlan.user_id == user_id,
        DailyPlan.date == target_date,
    )
    result = await db.execute(plan_stmt)
    plan = result.scalar_one_or_none()

    planned_ids = set()
    tasks_planned = 0
    if plan and plan.selected_task_ids:
        planned_ids = set(plan.selected_task_ids)
        tasks_planned = len(planned_ids)

    # Tasks planned AND completed
    tasks_planned_completed = len(planned_ids & completed_task_ids)

    planning_accuracy = 0.0
    if tasks_planned > 0:
        planning_accuracy = tasks_planned_completed / tasks_planned

    # Focus sessions for this date
    focus_stmt = select(FocusSession).where(
        FocusSession.user_id == user_id,
        cast(FocusSession.started_at, Date) == target_date,
        FocusSession.ended_at.isnot(None),
        FocusSession.duration.isnot(None),
    )
    result = await db.execute(focus_stmt)
    focus_sessions = list(result.scalars().all())
    focus_seconds_total = sum(fs.duration or 0 for fs in focus_sessions)

    # Focus seconds by goal (via goal_tracks_task edges)
    focus_by_goal: dict[str, int] = {}
    for fs in focus_sessions:
        # Find goals linked to this task
        goal_edge_stmt = select(Edge.source_id).where(
            Edge.target_id == fs.task_id,
            Edge.relation_type == EdgeRelationType.GOAL_TRACKS_TASK,
            Edge.state == EdgeState.ACTIVE,
        )
        result = await db.execute(goal_edge_stmt)
        for (goal_id,) in result.all():
            gid_str = str(goal_id)
            focus_by_goal[gid_str] = focus_by_goal.get(gid_str, 0) + (fs.duration or 0)

    # Journal mood for this date
    journal_mood_score = None
    journal_stmt = select(JournalNode.mood).where(
        JournalNode.node_id.in_(
            select(Node.id).where(
                Node.owner_id == user_id,
                Node.type == NodeType.JOURNAL_ENTRY,
            )
        ),
        JournalNode.entry_date == target_date,
    )
    result = await db.execute(journal_stmt)
    mood_row = result.scalar_one_or_none()
    if mood_row:
        journal_mood_score = MOOD_SCORE_MAP.get(mood_row, None)

    # Active goal progress delta
    active_goal_progress_delta = 0.0

    # Streak eligibility: at least one completed task
    streak_eligible = tasks_completed > 0

    # Upsert the rollup record
    existing_stmt = select(AnalyticsDailyRollup).where(
        AnalyticsDailyRollup.user_id == user_id,
        AnalyticsDailyRollup.date == target_date,
    )
    result = await db.execute(existing_stmt)
    rollup = result.scalar_one_or_none()

    if rollup is None:
        rollup = AnalyticsDailyRollup(
            user_id=user_id,
            date=target_date,
        )
        db.add(rollup)

    rollup.tasks_completed = tasks_completed
    rollup.tasks_planned = tasks_planned
    rollup.tasks_planned_completed = tasks_planned_completed
    rollup.planning_accuracy = planning_accuracy
    rollup.focus_seconds_total = focus_seconds_total
    rollup.focus_seconds_by_goal = focus_by_goal
    rollup.journal_mood_score = journal_mood_score
    rollup.active_goal_progress_delta = active_goal_progress_delta
    rollup.streak_eligible_flag = streak_eligible
    rollup.computed_at = datetime.now(timezone.utc)

    await db.flush()
    return rollup


async def compute_weekly_rollup(
    db: AsyncSession,
    user_id: uuid.UUID,
    week_start: date,
) -> AnalyticsWeeklyRollup:
    """
    Compute and persist a weekly rollup from daily rollups.
    Invariant D-02: Fully recomputable from daily rollups + progress_intelligence.
    """
    week_end = week_start + timedelta(days=6)

    # Get daily rollups for the week
    daily_stmt = select(AnalyticsDailyRollup).where(
        AnalyticsDailyRollup.user_id == user_id,
        AnalyticsDailyRollup.date >= week_start,
        AnalyticsDailyRollup.date <= week_end,
    )
    result = await db.execute(daily_stmt)
    dailies = list(result.scalars().all())

    total_completed = sum(d.tasks_completed for d in dailies)
    total_planned = sum(d.tasks_planned for d in dailies)
    total_planned_completed = sum(d.tasks_planned_completed for d in dailies)

    completion_rate = 0.0
    if total_planned > 0:
        completion_rate = total_completed / total_planned

    accuracy_values = [d.planning_accuracy for d in dailies if d.tasks_planned > 0]
    planning_accuracy = (sum(accuracy_values) / len(accuracy_values)) if accuracy_values else 0.0

    total_focus_time = sum(d.focus_seconds_total for d in dailies)

    # Aggregate goal time distribution
    goal_time_dist: dict[str, int] = {}
    for d in dailies:
        if d.focus_seconds_by_goal:
            for gid, secs in d.focus_seconds_by_goal.items():
                goal_time_dist[gid] = goal_time_dist.get(gid, 0) + secs

    # Momentum: total completed tasks this week (simple metric)
    momentum = float(total_completed)

    # Drift summary: current drift scores for active goals
    drift_summary = []
    goal_nodes_stmt = select(GoalNode.node_id).where(
        GoalNode.node_id.in_(
            select(Node.id).where(
                Node.owner_id == user_id,
                Node.type == NodeType.GOAL,
                Node.archived_at.is_(None),
            )
        ),
        GoalNode.status == GoalStatus.ACTIVE,
    )
    result = await db.execute(goal_nodes_stmt)
    active_goal_ids = [r[0] for r in result.all()]

    for goal_id in active_goal_ids:
        pi_stmt = select(ProgressIntelligence).where(
            ProgressIntelligence.node_id == goal_id
        )
        result = await db.execute(pi_stmt)
        pi = result.scalar_one_or_none()
        if pi:
            drift_summary.append({
                "goal_id": str(goal_id),
                "drift_score": pi.drift_score,
            })

    # Average mood
    mood_scores = [d.journal_mood_score for d in dailies if d.journal_mood_score is not None]
    avg_mood = (sum(mood_scores) / len(mood_scores)) if mood_scores else None

    # Mood-productivity correlation inputs
    correlation_inputs = []
    for d in dailies:
        if d.journal_mood_score is not None:
            correlation_inputs.append({
                "date": d.date.isoformat(),
                "mood_score": d.journal_mood_score,
                "tasks_completed": d.tasks_completed,
                "focus_seconds": d.focus_seconds_total,
            })

    # Upsert
    existing_stmt = select(AnalyticsWeeklyRollup).where(
        AnalyticsWeeklyRollup.user_id == user_id,
        AnalyticsWeeklyRollup.week_start_date == week_start,
    )
    result = await db.execute(existing_stmt)
    rollup = result.scalar_one_or_none()

    if rollup is None:
        rollup = AnalyticsWeeklyRollup(
            user_id=user_id,
            week_start_date=week_start,
        )
        db.add(rollup)

    rollup.completion_rate = completion_rate
    rollup.planning_accuracy = planning_accuracy
    rollup.total_focus_time = total_focus_time
    rollup.goal_time_distribution = goal_time_dist
    rollup.momentum = momentum
    rollup.drift_summary = drift_summary
    rollup.avg_mood = avg_mood
    rollup.mood_productivity_correlation_inputs = correlation_inputs
    rollup.computed_at = datetime.now(timezone.utc)

    await db.flush()
    return rollup


async def compute_rollups_for_range(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> tuple[list[AnalyticsDailyRollup], list[AnalyticsWeeklyRollup]]:
    """
    Compute daily + weekly rollups for a date range.
    Useful for backfilling historical data.
    """
    daily_rollups = []
    current = start_date
    while current <= end_date:
        rollup = await compute_daily_rollup(db, user_id, current)
        daily_rollups.append(rollup)
        current += timedelta(days=1)

    # Compute weekly rollups for each Monday in the range
    weekly_rollups = []
    # Find the Monday on or before start_date
    monday = start_date - timedelta(days=start_date.weekday())
    while monday <= end_date:
        rollup = await compute_weekly_rollup(db, user_id, monday)
        weekly_rollups.append(rollup)
        monday += timedelta(days=7)

    return daily_rollups, weekly_rollups


# =============================================================================
# Tier B: Query pre-aggregated rollups
# =============================================================================


async def get_daily_rollups(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[AnalyticsDailyRollup]:
    """Get pre-aggregated daily rollups for a date range."""
    stmt = select(AnalyticsDailyRollup).where(
        AnalyticsDailyRollup.user_id == user_id,
        AnalyticsDailyRollup.date >= start_date,
        AnalyticsDailyRollup.date <= end_date,
    ).order_by(AnalyticsDailyRollup.date)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_weekly_rollups(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> list[AnalyticsWeeklyRollup]:
    """Get pre-aggregated weekly rollups for a date range."""
    stmt = select(AnalyticsWeeklyRollup).where(
        AnalyticsWeeklyRollup.user_id == user_id,
        AnalyticsWeeklyRollup.week_start_date >= start_date,
        AnalyticsWeeklyRollup.week_start_date <= end_date,
    ).order_by(AnalyticsWeeklyRollup.week_start_date)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# =============================================================================
# Analytics insight generation (Section 4.7)
# Invariant D-04: Every output classified as descriptive/correlational/recommendation
# =============================================================================


def compute_planning_accuracy_insight(
    daily_rollups: list[AnalyticsDailyRollup],
) -> AnalyticsOutput | None:
    """
    Plan vs actual analysis.
    Invariant D-04: classified as descriptive.
    """
    days_with_plans = [d for d in daily_rollups if d.tasks_planned > 0]
    if not days_with_plans:
        return None

    avg_accuracy = sum(d.planning_accuracy for d in days_with_plans) / len(days_with_plans)
    total_planned = sum(d.tasks_planned for d in days_with_plans)
    total_completed = sum(d.tasks_planned_completed for d in days_with_plans)

    return AnalyticsOutput(
        classification="descriptive",
        label="",  # Descriptive: no label
        explanation=DerivedExplanation(
            summary=f"Planning accuracy: {avg_accuracy:.0%} — completed {total_completed} of {total_planned} planned tasks.",
            factors=[
                DerivedFactor(signal="avg_planning_accuracy", value=round(avg_accuracy, 3), weight=1.0),
                DerivedFactor(signal="total_planned", value=total_planned, weight=0.5),
                DerivedFactor(signal="total_completed", value=total_completed, weight=0.5),
                DerivedFactor(signal="days_with_plans", value=len(days_with_plans), weight=0.3),
            ],
            confidence=None,
            generated_at=datetime.now(timezone.utc),
            version="v1",
        ),
        data={
            "avg_accuracy": round(avg_accuracy, 3),
            "total_planned": total_planned,
            "total_completed": total_completed,
            "days_with_plans": len(days_with_plans),
        },
    )


def compute_mood_productivity_correlation(
    weekly_rollups: list[AnalyticsWeeklyRollup],
) -> AnalyticsOutput | None:
    """
    Mood / productivity correlation analysis.
    Invariant D-04: classified as correlational — never implies causation.
    """
    all_inputs = []
    for wr in weekly_rollups:
        if wr.mood_productivity_correlation_inputs:
            all_inputs.extend(wr.mood_productivity_correlation_inputs)

    if len(all_inputs) < 5:
        return None  # Not enough data

    mood_values = [i["mood_score"] for i in all_inputs]
    task_values = [i["tasks_completed"] for i in all_inputs]

    # Simple Pearson correlation
    n = len(mood_values)
    mean_mood = sum(mood_values) / n
    mean_tasks = sum(task_values) / n

    num = sum((m - mean_mood) * (t - mean_tasks) for m, t in zip(mood_values, task_values))
    den_mood = sum((m - mean_mood) ** 2 for m in mood_values) ** 0.5
    den_tasks = sum((t - mean_tasks) ** 2 for t in task_values) ** 0.5

    if den_mood == 0 or den_tasks == 0:
        return None

    correlation = num / (den_mood * den_tasks)

    # Invariant D-04: correlational — "Pattern detected", never implies causation
    if abs(correlation) < 0.3:
        direction = "no significant"
    elif correlation > 0:
        direction = "a positive"
    else:
        direction = "a negative"

    return AnalyticsOutput(
        classification="correlational",
        label="Pattern detected",  # Invariant D-04: correlational label
        explanation=DerivedExplanation(
            summary=f"There is {direction} correlation (r={correlation:.2f}) between mood and task completion.",
            factors=[
                DerivedFactor(signal="pearson_r", value=round(correlation, 3), weight=1.0),
                DerivedFactor(signal="data_points", value=n, weight=0.5),
                DerivedFactor(signal="avg_mood", value=round(mean_mood, 2), weight=0.3),
                DerivedFactor(signal="avg_tasks_completed", value=round(mean_tasks, 2), weight=0.3),
            ],
            confidence=min(1.0, n / 30),  # More data = more confidence
            generated_at=datetime.now(timezone.utc),
            version="v1",
        ),
        data={
            "correlation": round(correlation, 3),
            "data_points": n,
            "avg_mood": round(mean_mood, 2),
            "avg_tasks_completed": round(mean_tasks, 2),
        },
    )


def generate_completion_recommendation(
    daily_rollups: list[AnalyticsDailyRollup],
) -> AnalyticsOutput | None:
    """
    Generate a recommendation based on completion patterns.
    Invariant D-04: classified as recommendation — must cite correlation, must be dismissible.
    """
    if len(daily_rollups) < 7:
        return None

    # Check if there's a pattern in streak-eligible days
    streak_days = [d for d in daily_rollups if d.streak_eligible_flag]
    non_streak_days = [d for d in daily_rollups if not d.streak_eligible_flag]

    if not streak_days or not non_streak_days:
        return None

    avg_focus_streak = (
        sum(d.focus_seconds_total for d in streak_days) / len(streak_days)
    )
    avg_focus_non_streak = (
        sum(d.focus_seconds_total for d in non_streak_days) / len(non_streak_days)
    )

    if avg_focus_non_streak == 0 or avg_focus_streak <= avg_focus_non_streak:
        return None

    ratio = avg_focus_streak / avg_focus_non_streak

    if ratio < 1.3:
        return None  # Not a strong enough pattern

    return AnalyticsOutput(
        classification="recommendation",
        label="Suggestion",  # Invariant D-04: recommendation label
        explanation=DerivedExplanation(
            summary=(
                f"On days when you complete at least one task, "
                f"you tend to focus {ratio:.1f}x longer. "
                f"Consider starting with a small task to build momentum."
            ),
            factors=[
                DerivedFactor(signal="avg_focus_streak_days", value=round(avg_focus_streak), weight=0.6),
                DerivedFactor(signal="avg_focus_non_streak_days", value=round(avg_focus_non_streak), weight=0.4),
                DerivedFactor(signal="focus_ratio", value=round(ratio, 2), weight=1.0),
            ],
            confidence=min(1.0, len(daily_rollups) / 30),
            generated_at=datetime.now(timezone.utc),
            version="v1",
        ),
        data={
            "focus_ratio": round(ratio, 2),
            "streak_days_count": len(streak_days),
            "non_streak_days_count": len(non_streak_days),
            "avg_focus_streak": round(avg_focus_streak),
            "avg_focus_non_streak": round(avg_focus_non_streak),
        },
    )
