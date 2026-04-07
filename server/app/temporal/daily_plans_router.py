"""
Daily plans router (Section 8.3 — Temporal layer).
Endpoints: GET /api/daily-plans, POST /api/daily-plans

Invariant T-04: Ownership alignment enforced via service layer.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.temporal.daily_plans_service import (
    create_daily_plan,
    get_daily_plan,
    get_daily_plan_by_id,
    list_daily_plans,
    close_daily_plan,
)

router = APIRouter(prefix="/api/daily-plans", tags=["daily-plans"])


class DailyPlanCreateRequest(BaseModel):
    date: date | None = None  # Defaults to today
    selected_task_ids: list[str]
    intention_text: str | None = None


class DailyPlanResponse(BaseModel):
    id: str
    user_id: str
    date: str
    selected_task_ids: list[str]
    intention_text: str | None
    created_at: str
    closed_at: str | None


class DailyPlanListResponse(BaseModel):
    items: list[DailyPlanResponse]
    total: int


def _plan_to_response(plan) -> DailyPlanResponse:
    return DailyPlanResponse(
        id=str(plan.id),
        user_id=str(plan.user_id),
        date=plan.date.isoformat(),
        selected_task_ids=[str(tid) for tid in plan.selected_task_ids],
        intention_text=plan.intention_text,
        created_at=plan.created_at.isoformat(),
        closed_at=plan.closed_at.isoformat() if plan.closed_at else None,
    )


@router.post("", response_model=DailyPlanResponse)
async def create_plan(
    req: DailyPlanCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create or update a daily plan.
    Layer: Temporal.
    Invariant T-04: Ownership alignment enforced.
    """
    plan_date = req.date or date.today()
    task_ids = [uuid.UUID(tid) for tid in req.selected_task_ids]

    try:
        plan = await create_daily_plan(
            db, user.id, plan_date, task_ids, req.intention_text,
        )
        return _plan_to_response(plan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=DailyPlanListResponse)
async def list_plans(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List daily plans, most recent first. Layer: Temporal."""
    plans, total = await list_daily_plans(db, user.id, limit, offset)
    return DailyPlanListResponse(
        items=[_plan_to_response(p) for p in plans],
        total=total,
    )


@router.get("/today", response_model=DailyPlanResponse | None)
async def get_today_plan(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get today's daily plan, if it exists."""
    plan = await get_daily_plan(db, user.id, date.today())
    if plan is None:
        return None
    return _plan_to_response(plan)


@router.get("/{plan_date}", response_model=DailyPlanResponse | None)
async def get_plan_by_date(
    plan_date: date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a daily plan for a specific date."""
    plan = await get_daily_plan(db, user.id, plan_date)
    if plan is None:
        return None
    return _plan_to_response(plan)


@router.post("/{plan_date}/close", response_model=DailyPlanResponse)
async def close_plan(
    plan_date: date,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Close a daily plan (sets closed_at). Used during evening reflection."""
    plan = await close_daily_plan(db, user.id, plan_date)
    if plan is None:
        raise HTTPException(status_code=404, detail="No plan found for this date")
    return _plan_to_response(plan)
