"""
Evening reflection behavioral workflow (Section 5.1).
Reflect stage of the 4-stage daily cycle: commit -> execute -> reflect -> learn.

Workflow:
1. Compare daily_plan vs actual task completion (join: task_execution_events
   via task_id + expected_for_date = daily_plans.date)
2. Quick reflection prompts
3. Output: feedback into journal + derived metrics + execution events for
   skipped/deferred tasks

Invariant T-01: No temporal-to-temporal FKs (joins through Core task_id).
Invariant T-04: Ownership alignment.
Invariant S-04: One terminal event per task per date.
"""

import uuid
from datetime import date, datetime, timezone
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, TaskNode
from server.app.core.models.enums import NodeType, TaskStatus, TaskExecutionEventType
from server.app.temporal.models import DailyPlan, FocusSession
from server.app.temporal.daily_plans_service import get_daily_plan, close_daily_plan
from server.app.temporal.execution_events_service import (
    list_execution_events,
    create_execution_event,
)
from server.app.temporal.focus_sessions_service import get_focus_time_for_date


@dataclass
class TaskReflectionItem:
    """A task from the daily plan with its actual completion status."""
    node_id: str
    title: str
    priority: str
    status: str  # current task status
    was_planned: bool
    event_type: str | None  # completed/skipped/deferred or None if no event
    focus_time_seconds: int  # Focus time spent on this task today
    notes: str | None = None


@dataclass
class ReflectionPrompt:
    """A reflection prompt for the user."""
    prompt_id: str
    text: str
    category: str  # completion, blockers, gratitude, tomorrow


@dataclass
class EveningReflectionData:
    """Complete evening reflection data for the UI."""
    date: date
    plan_exists: bool
    planned_tasks: list[TaskReflectionItem]
    unplanned_completed: list[TaskReflectionItem]  # Tasks completed but not in plan
    total_planned: int
    total_completed: int
    total_focus_time_seconds: int
    completion_rate: float  # 0.0-1.0
    prompts: list[ReflectionPrompt]
    plan_id: str | None = None
    intention_text: str | None = None


def _get_reflection_prompts(
    completion_rate: float,
    total_planned: int,
    total_completed: int,
) -> list[ReflectionPrompt]:
    """Generate contextual reflection prompts based on the day's data."""
    prompts = []

    # Completion-based prompts
    if completion_rate >= 0.8:
        prompts.append(ReflectionPrompt(
            prompt_id="completion_high",
            text="Great day! What helped you stay focused and productive?",
            category="completion",
        ))
    elif completion_rate >= 0.5:
        prompts.append(ReflectionPrompt(
            prompt_id="completion_mid",
            text="You made solid progress. What would help you complete the remaining tasks?",
            category="completion",
        ))
    elif total_planned > 0:
        prompts.append(ReflectionPrompt(
            prompt_id="completion_low",
            text="Some tasks remain. Were there unexpected blockers, or was the plan too ambitious?",
            category="completion",
        ))

    # Blocker prompt
    if total_planned > total_completed and total_planned > 0:
        prompts.append(ReflectionPrompt(
            prompt_id="blockers",
            text="What got in the way of completing your planned tasks?",
            category="blockers",
        ))

    # Gratitude prompt
    prompts.append(ReflectionPrompt(
        prompt_id="gratitude",
        text="What's one thing you're grateful for today?",
        category="gratitude",
    ))

    # Tomorrow prompt
    prompts.append(ReflectionPrompt(
        prompt_id="tomorrow",
        text="What's the most important thing to tackle tomorrow?",
        category="tomorrow",
    ))

    return prompts


async def get_evening_reflection(
    db: AsyncSession,
    owner_id: uuid.UUID,
    reflection_date: date | None = None,
) -> EveningReflectionData:
    """
    Assemble evening reflection data.
    Compares daily_plan vs actual task_execution_events for the day.

    Invariant T-01: Joins through Core task_id, not temporal-to-temporal.
    """
    target_date = reflection_date or date.today()
    now = datetime.now(timezone.utc)

    # Get today's plan
    plan = await get_daily_plan(db, owner_id, target_date)

    # Get execution events for today
    events, _ = await list_execution_events(
        db, owner_id, expected_for_date=target_date, limit=100,
    )
    events_by_task = {e.task_id: e for e in events}

    # Get total focus time for the day
    total_focus_time = await get_focus_time_for_date(db, owner_id, now)

    # Get per-task focus time
    from sqlalchemy import select as sa_select
    focus_stmt = (
        sa_select(
            FocusSession.task_id,
            func.coalesce(func.sum(FocusSession.duration), 0).label("total"),
        )
        .where(
            FocusSession.user_id == owner_id,
            FocusSession.started_at >= datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            FocusSession.started_at < datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc),
            FocusSession.ended_at.isnot(None),
        )
        .group_by(FocusSession.task_id)
    )
    focus_result = await db.execute(focus_stmt)
    focus_by_task = {row[0]: row[1] for row in focus_result.all()}

    planned_tasks: list[TaskReflectionItem] = []
    planned_task_ids: set[uuid.UUID] = set()

    if plan:
        planned_task_ids = set(plan.selected_task_ids)

        # Fetch task details for planned tasks
        if plan.selected_task_ids:
            stmt = (
                select(Node, TaskNode)
                .join(TaskNode, TaskNode.node_id == Node.id)
                .where(Node.id.in_(plan.selected_task_ids))
            )
            result = await db.execute(stmt)
            task_rows = {n.id: (n, t) for n, t in result.all()}

            for tid in plan.selected_task_ids:
                if tid in task_rows:
                    node, task = task_rows[tid]
                    event = events_by_task.get(tid)
                    planned_tasks.append(TaskReflectionItem(
                        node_id=str(tid),
                        title=node.title,
                        priority=task.priority.value,
                        status=task.status.value,
                        was_planned=True,
                        event_type=event.event_type.value if event else None,
                        focus_time_seconds=focus_by_task.get(tid, 0),
                    ))

    # Find tasks completed today that were NOT in the plan
    completed_event_tasks = [
        e for e in events
        if e.event_type == TaskExecutionEventType.COMPLETED
        and e.task_id not in planned_task_ids
    ]

    unplanned_completed: list[TaskReflectionItem] = []
    if completed_event_tasks:
        unplanned_ids = [e.task_id for e in completed_event_tasks]
        stmt = (
            select(Node, TaskNode)
            .join(TaskNode, TaskNode.node_id == Node.id)
            .where(Node.id.in_(unplanned_ids))
        )
        result = await db.execute(stmt)
        for node, task in result.all():
            event = events_by_task.get(node.id)
            unplanned_completed.append(TaskReflectionItem(
                node_id=str(node.id),
                title=node.title,
                priority=task.priority.value,
                status=task.status.value,
                was_planned=False,
                event_type=event.event_type.value if event else "completed",
                focus_time_seconds=focus_by_task.get(node.id, 0),
            ))

    # Compute completion rate
    total_planned = len(planned_tasks)
    total_completed_planned = sum(
        1 for t in planned_tasks if t.event_type == "completed"
    )
    completion_rate = (
        total_completed_planned / total_planned if total_planned > 0 else 0.0
    )

    total_completed_all = total_completed_planned + len(unplanned_completed)

    # Generate reflection prompts
    prompts = _get_reflection_prompts(
        completion_rate, total_planned, total_completed_all,
    )

    return EveningReflectionData(
        date=target_date,
        plan_exists=plan is not None,
        planned_tasks=planned_tasks,
        unplanned_completed=unplanned_completed,
        total_planned=total_planned,
        total_completed=total_completed_all,
        total_focus_time_seconds=total_focus_time,
        completion_rate=completion_rate,
        prompts=prompts,
        plan_id=str(plan.id) if plan else None,
        intention_text=plan.intention_text if plan else None,
    )


async def submit_reflection(
    db: AsyncSession,
    owner_id: uuid.UUID,
    skipped_task_ids: list[uuid.UUID] | None = None,
    deferred_task_ids: list[uuid.UUID] | None = None,
    reflection_notes: str | None = None,
    reflection_date: date | None = None,
) -> dict:
    """
    Submit evening reflection results.
    Creates execution events for skipped/deferred tasks.
    Closes the daily plan.

    Invariant S-04: One terminal event per task per date.
    """
    target_date = reflection_date or date.today()

    results = {
        "skipped": [],
        "deferred": [],
        "plan_closed": False,
        "errors": [],
    }

    # Create execution events for skipped tasks
    for task_id in (skipped_task_ids or []):
        try:
            await create_execution_event(
                db, owner_id, task_id,
                TaskExecutionEventType.SKIPPED,
                target_date,
                notes=reflection_notes,
            )
            results["skipped"].append(str(task_id))
        except ValueError as e:
            # Invariant S-04: Event may already exist
            results["errors"].append(f"Skip {task_id}: {str(e)}")

    # Create execution events for deferred tasks
    for task_id in (deferred_task_ids or []):
        try:
            await create_execution_event(
                db, owner_id, task_id,
                TaskExecutionEventType.DEFERRED,
                target_date,
                notes=reflection_notes,
            )
            results["deferred"].append(str(task_id))
        except ValueError as e:
            # Invariant S-04: Event may already exist
            results["errors"].append(f"Defer {task_id}: {str(e)}")

    # Close the daily plan
    plan = await close_daily_plan(db, owner_id, target_date)
    results["plan_closed"] = plan is not None

    return results
