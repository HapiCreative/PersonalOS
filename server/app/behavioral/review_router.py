"""
Review behavioral router (Section 8.3, Phase 8).
Endpoints:
  GET /api/review/weekly — Get weekly review summary
  POST /api/review/weekly — Save weekly snapshot
  GET /api/review/monthly — Get monthly review summary
  POST /api/review/monthly — Save monthly snapshot
Layer: Behavioral (assembly from Core + Derived + Temporal data)
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
from server.app.behavioral.weekly_review import (
    get_weekly_review_summary,
    save_weekly_snapshot,
    WeeklyTaskSummary,
    WeeklyGoalSummary,
)
from server.app.behavioral.monthly_review import (
    get_monthly_review_summary,
    save_monthly_snapshot,
    MonthlyGoalSummary,
    WeeklySnapshotSummary,
)

router = APIRouter(prefix="/api/review", tags=["review"])


# =============================================================================
# Weekly Review schemas
# =============================================================================


class WeeklyTaskSummaryResponse(BaseModel):
    node_id: str
    title: str
    status: str
    priority: str
    completed: bool
    was_planned: bool


class WeeklyGoalSummaryResponse(BaseModel):
    node_id: str
    title: str
    status: str
    progress: float
    linked_task_count: int
    completed_task_count: int


class WeeklyReviewSummaryResponse(BaseModel):
    week_start: date
    week_end: date
    completed_tasks: list[WeeklyTaskSummaryResponse]
    planned_tasks: list[WeeklyTaskSummaryResponse]
    stalled_goals: list[WeeklyGoalSummaryResponse]
    active_goals: list[WeeklyGoalSummaryResponse]
    total_planned: int
    total_completed: int
    completion_rate: float
    total_focus_time_seconds: int
    existing_snapshot: dict | None = None


class WeeklySnapshotRequest(BaseModel):
    focus_areas: list[str] = Field(min_length=0)
    priority_task_ids: list[str] | None = None
    notes: str | None = None
    reference_date: date | None = None


class WeeklySnapshotResponse(BaseModel):
    id: str
    week_start_date: str
    week_end_date: str
    focus_areas: list[str]
    priority_task_ids: list[str]
    notes: str | None
    created_at: str


# =============================================================================
# Monthly Review schemas
# =============================================================================


class MonthlyGoalSummaryResponse(BaseModel):
    node_id: str
    title: str
    status: str
    progress: float
    tasks_completed_this_month: int


class WeeklySnapshotBriefResponse(BaseModel):
    week_start: date
    week_end: date
    focus_areas: list[str]
    notes: str | None = None


class MonthlyReviewSummaryResponse(BaseModel):
    month: date
    month_name: str
    weekly_snapshots: list[WeeklySnapshotBriefResponse]
    goals: list[MonthlyGoalSummaryResponse]
    total_tasks_completed: int
    total_focus_time_seconds: int
    existing_snapshot: dict | None = None


class MonthlySnapshotRequest(BaseModel):
    focus_areas: list[str] = Field(min_length=0)
    notes: str | None = None
    reference_date: date | None = None


class MonthlySnapshotResponse(BaseModel):
    id: str
    month: str
    focus_areas: list[str]
    notes: str | None
    created_at: str


# =============================================================================
# Weekly Review endpoints
# =============================================================================


@router.get("/weekly", response_model=WeeklyReviewSummaryResponse)
async def get_weekly_review(
    reference_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the weekly review summary.
    Includes completed vs planned tasks, goal progress, stalled goals.
    Layer: Behavioral.
    """
    summary = await get_weekly_review_summary(db, user.id, reference_date)
    return WeeklyReviewSummaryResponse(
        week_start=summary.week_start,
        week_end=summary.week_end,
        completed_tasks=[
            WeeklyTaskSummaryResponse(
                node_id=str(t.node_id),
                title=t.title,
                status=t.status,
                priority=t.priority,
                completed=t.completed,
                was_planned=t.was_planned,
            )
            for t in summary.completed_tasks
        ],
        planned_tasks=[
            WeeklyTaskSummaryResponse(
                node_id=str(t.node_id),
                title=t.title,
                status=t.status,
                priority=t.priority,
                completed=t.completed,
                was_planned=t.was_planned,
            )
            for t in summary.planned_tasks
        ],
        stalled_goals=[
            WeeklyGoalSummaryResponse(
                node_id=str(g.node_id),
                title=g.title,
                status=g.status,
                progress=g.progress,
                linked_task_count=g.linked_task_count,
                completed_task_count=g.completed_task_count,
            )
            for g in summary.stalled_goals
        ],
        active_goals=[
            WeeklyGoalSummaryResponse(
                node_id=str(g.node_id),
                title=g.title,
                status=g.status,
                progress=g.progress,
                linked_task_count=g.linked_task_count,
                completed_task_count=g.completed_task_count,
            )
            for g in summary.active_goals
        ],
        total_planned=summary.total_planned,
        total_completed=summary.total_completed,
        completion_rate=summary.completion_rate,
        total_focus_time_seconds=summary.total_focus_time_seconds,
        existing_snapshot=summary.existing_snapshot,
    )


@router.post("/weekly", response_model=WeeklySnapshotResponse)
async def save_weekly_review(
    req: WeeklySnapshotRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save the weekly review as a weekly_snapshots record.
    Guided workflow output: focus areas, priority tasks for next week, notes.
    Layer: Behavioral -> Temporal.
    """
    task_ids = [uuid.UUID(tid) for tid in req.priority_task_ids] if req.priority_task_ids else None

    snapshot = await save_weekly_snapshot(
        db, user.id, req.focus_areas, task_ids, req.notes, req.reference_date,
    )
    return WeeklySnapshotResponse(
        id=str(snapshot.id),
        week_start_date=snapshot.week_start_date.isoformat(),
        week_end_date=snapshot.week_end_date.isoformat(),
        focus_areas=snapshot.focus_areas,
        priority_task_ids=[str(tid) for tid in (snapshot.priority_task_ids or [])],
        notes=snapshot.notes,
        created_at=snapshot.created_at.isoformat(),
    )


# =============================================================================
# Monthly Review endpoints
# =============================================================================


@router.get("/monthly", response_model=MonthlyReviewSummaryResponse)
async def get_monthly_review(
    reference_date: Optional[date] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the monthly review summary.
    References the month's weekly snapshots and goal progress.
    Layer: Behavioral.
    """
    summary = await get_monthly_review_summary(db, user.id, reference_date)
    return MonthlyReviewSummaryResponse(
        month=summary.month,
        month_name=summary.month_name,
        weekly_snapshots=[
            WeeklySnapshotBriefResponse(
                week_start=w.week_start,
                week_end=w.week_end,
                focus_areas=w.focus_areas,
                notes=w.notes,
            )
            for w in summary.weekly_snapshots
        ],
        goals=[
            MonthlyGoalSummaryResponse(
                node_id=str(g.node_id),
                title=g.title,
                status=g.status,
                progress=g.progress,
                tasks_completed_this_month=g.tasks_completed_this_month,
            )
            for g in summary.goals
        ],
        total_tasks_completed=summary.total_tasks_completed,
        total_focus_time_seconds=summary.total_focus_time_seconds,
        existing_snapshot=summary.existing_snapshot,
    )


@router.post("/monthly", response_model=MonthlySnapshotResponse)
async def save_monthly_review(
    req: MonthlySnapshotRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save the monthly review as a monthly_snapshots record.
    Strategic reflection: focus areas, notes.
    Layer: Behavioral -> Temporal.
    """
    snapshot = await save_monthly_snapshot(
        db, user.id, req.focus_areas, req.notes, req.reference_date,
    )
    return MonthlySnapshotResponse(
        id=str(snapshot.id),
        month=snapshot.month.isoformat(),
        focus_areas=snapshot.focus_areas,
        notes=snapshot.notes,
        created_at=snapshot.created_at.isoformat(),
    )
