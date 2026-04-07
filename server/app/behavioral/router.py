"""
Behavioral layer router (Section 8.3).
Endpoints: GET /api/today, POST /api/today/commit, GET /api/today/suggestions,
           GET /api/today/reflection, POST /api/today/reflection
Layer: Behavioral (read-only assembly from Core + Derived data)
"""

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.behavioral.today import assemble_today_view, TodayItem
from server.app.behavioral.morning_commit import (
    get_morning_suggestions,
    commit_morning_plan,
    SuggestedTask,
)
from server.app.behavioral.evening_reflection import (
    get_evening_reflection,
    submit_reflection,
)

router = APIRouter(prefix="/api/today", tags=["today"])


class TodayItemResponse(BaseModel):
    section: str
    item_type: str
    node_id: str | None = None
    title: str
    subtitle: str = ""
    priority: str | None = None
    due_date: date | None = None
    progress: float | None = None
    is_unsolicited: bool = False
    metadata: dict = Field(default_factory=dict)


class TodaySectionResponse(BaseModel):
    name: str
    items: list[TodayItemResponse]


class TodayViewResponse(BaseModel):
    """
    Today View behavioral surface response.
    Invariant U-02: total_count <= 10.
    Invariant U-04: per-section caps enforced.
    """
    items: list[TodayItemResponse]
    total_count: int
    sections: list[TodaySectionResponse]
    stage: str
    date: date
    has_plan: bool = False  # Phase 7: whether morning commitment exists
    active_focus_task_id: str | None = None  # Phase 7: task in active focus session


def _item_to_response(item: TodayItem) -> TodayItemResponse:
    return TodayItemResponse(
        section=item.section,
        item_type=item.item_type,
        node_id=str(item.node_id) if item.node_id else None,
        title=item.title,
        subtitle=item.subtitle,
        priority=item.priority,
        due_date=item.due_date,
        progress=item.progress,
        is_unsolicited=item.is_unsolicited,
        metadata=item.metadata,
    )


@router.get("", response_model=TodayViewResponse)
async def get_today_view(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the Today View behavioral surface.

    Invariant U-01: Max 2 unsolicited intelligence items.
    Invariant U-02: Hard cap of 10 items.
    Invariant U-04: Per-section caps enforced.
    Invariant U-05: Suppression precedence applied.
    """
    result = await assemble_today_view(db, user.id)

    items = [_item_to_response(item) for item in result.items]

    section_order = ["focus", "due", "habits", "learning", "goal_nudges", "review", "resurfaced", "journal"]
    sections = []
    for section_name in section_order:
        section_items = result.sections.get(section_name, [])
        if section_items:
            sections.append(TodaySectionResponse(
                name=section_name,
                items=[_item_to_response(item) for item in section_items],
            ))

    return TodayViewResponse(
        items=items,
        total_count=result.total_count,
        sections=sections,
        stage=result.stage,
        date=result.date,
        has_plan=result.has_plan,
        active_focus_task_id=str(result.active_focus_task_id) if result.active_focus_task_id else None,
    )


# =============================================================================
# Phase 7: Morning Commit + Evening Reflection endpoints
# =============================================================================


class SuggestedTaskResponse(BaseModel):
    node_id: str
    title: str
    priority: str
    due_date: date | None = None
    status: str
    is_recurring: bool
    signal_score: float | None = None
    reason: str
    goal_title: str | None = None


class MorningCommitSuggestionsResponse(BaseModel):
    suggested_tasks: list[SuggestedTaskResponse]
    existing_plan: dict | None = None
    date: date
    ai_briefing: list[str]


class CommitRequest(BaseModel):
    selected_task_ids: list[str]
    intention_text: str | None = None


class CommitResponse(BaseModel):
    id: str
    date: str
    selected_task_ids: list[str]
    intention_text: str | None
    created_at: str
    closed_at: str | None


class TaskReflectionItemResponse(BaseModel):
    node_id: str
    title: str
    priority: str
    status: str
    was_planned: bool
    event_type: str | None = None
    focus_time_seconds: int
    notes: str | None = None


class ReflectionPromptResponse(BaseModel):
    prompt_id: str
    text: str
    category: str


class EveningReflectionResponse(BaseModel):
    date: date
    plan_exists: bool
    planned_tasks: list[TaskReflectionItemResponse]
    unplanned_completed: list[TaskReflectionItemResponse]
    total_planned: int
    total_completed: int
    total_focus_time_seconds: int
    completion_rate: float
    prompts: list[ReflectionPromptResponse]
    plan_id: str | None = None
    intention_text: str | None = None


class ReflectionSubmitRequest(BaseModel):
    skipped_task_ids: list[str] = Field(default_factory=list)
    deferred_task_ids: list[str] = Field(default_factory=list)
    reflection_notes: str | None = None


class ReflectionSubmitResponse(BaseModel):
    skipped: list[str]
    deferred: list[str]
    plan_closed: bool
    errors: list[str]


@router.get("/suggestions", response_model=MorningCommitSuggestionsResponse)
async def get_suggestions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get system-suggested tasks for morning commit.
    Aggregates by: overdue, due today, high signal score, goal drift.
    Layer: Behavioral.
    """
    result = await get_morning_suggestions(db, user.id)
    return MorningCommitSuggestionsResponse(
        suggested_tasks=[
            SuggestedTaskResponse(
                node_id=str(s.node_id),
                title=s.title,
                priority=s.priority,
                due_date=s.due_date,
                status=s.status,
                is_recurring=s.is_recurring,
                signal_score=s.signal_score,
                reason=s.reason,
                goal_title=s.goal_title,
            )
            for s in result.suggested_tasks
        ],
        existing_plan=result.existing_plan,
        date=result.date,
        ai_briefing=result.ai_briefing,
    )


@router.post("/commit", response_model=CommitResponse)
async def commit_plan(
    req: CommitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Commit morning plan: select 1-3 priorities + optional intention.
    Creates or updates daily_plans record.
    Layer: Behavioral -> Temporal.
    """
    task_ids = [uuid.UUID(tid) for tid in req.selected_task_ids]

    try:
        result = await commit_morning_plan(
            db, user.id, task_ids, req.intention_text,
        )
        return CommitResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reflection", response_model=EveningReflectionResponse)
async def get_reflection(
    reflection_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get evening reflection data: plan vs actual comparison.
    Layer: Behavioral.
    """
    result = await get_evening_reflection(db, user.id, reflection_date)
    return EveningReflectionResponse(
        date=result.date,
        plan_exists=result.plan_exists,
        planned_tasks=[
            TaskReflectionItemResponse(
                node_id=t.node_id,
                title=t.title,
                priority=t.priority,
                status=t.status,
                was_planned=t.was_planned,
                event_type=t.event_type,
                focus_time_seconds=t.focus_time_seconds,
                notes=t.notes,
            )
            for t in result.planned_tasks
        ],
        unplanned_completed=[
            TaskReflectionItemResponse(
                node_id=t.node_id,
                title=t.title,
                priority=t.priority,
                status=t.status,
                was_planned=t.was_planned,
                event_type=t.event_type,
                focus_time_seconds=t.focus_time_seconds,
                notes=t.notes,
            )
            for t in result.unplanned_completed
        ],
        total_planned=result.total_planned,
        total_completed=result.total_completed,
        total_focus_time_seconds=result.total_focus_time_seconds,
        completion_rate=result.completion_rate,
        prompts=[
            ReflectionPromptResponse(
                prompt_id=p.prompt_id,
                text=p.text,
                category=p.category,
            )
            for p in result.prompts
        ],
        plan_id=result.plan_id,
        intention_text=result.intention_text,
    )


@router.post("/reflection", response_model=ReflectionSubmitResponse)
async def submit_reflection_endpoint(
    req: ReflectionSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit evening reflection: mark skipped/deferred tasks, close plan.
    Creates execution events for skipped/deferred tasks.
    Layer: Behavioral -> Temporal.

    Invariant S-04: One terminal event per task per date.
    """
    skipped = [uuid.UUID(tid) for tid in req.skipped_task_ids] if req.skipped_task_ids else None
    deferred = [uuid.UUID(tid) for tid in req.deferred_task_ids] if req.deferred_task_ids else None

    result = await submit_reflection(
        db, user.id, skipped, deferred, req.reflection_notes,
    )
    return ReflectionSubmitResponse(**result)
