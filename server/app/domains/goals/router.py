"""
Goals domain router (Section 8.3).
Endpoints: POST/GET /api/goals, GET /api/goals/{id}, PUT /api/goals/{id}
Layer: Core (read/write) + Derived (progress computation)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import GoalStatus
from server.app.domains.goals.schemas import (
    GoalCreate,
    GoalListResponse,
    GoalResponse,
    GoalUpdate,
    GoalWithTasksResponse,
    GoalLinkedTaskResponse,
)
from server.app.domains.goals.service import (
    create_goal,
    get_goal,
    list_goals,
    update_goal,
    get_goal_linked_tasks,
    refresh_goal_progress,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _to_response(node, goal) -> GoalResponse:
    return GoalResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        status=goal.status,
        start_date=goal.start_date,
        end_date=goal.end_date,
        timeframe_label=goal.timeframe_label,
        progress=goal.progress,
        milestones=goal.milestones if isinstance(goal.milestones, list) else [],
        notes=goal.notes,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal_endpoint(
    body: GoalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new goal."""
    node, goal = await create_goal(
        db, user.id, body.title, body.summary,
        body.status, body.start_date, body.end_date,
        body.timeframe_label, body.milestones, body.notes,
    )
    return _to_response(node, goal)


@router.get("", response_model=GoalListResponse)
async def list_goals_endpoint(
    status_filter: GoalStatus | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List goals with optional filters."""
    items, total = await list_goals(
        db, user.id, status_filter, include_archived, limit, offset,
    )
    return GoalListResponse(
        items=[_to_response(n, g) for n, g in items],
        total=total,
    )


@router.get("/{node_id}", response_model=GoalWithTasksResponse)
async def get_goal_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single goal by node ID, including linked tasks."""
    pair = await get_goal(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    node, goal = pair

    # Refresh progress on read (Invariant D-03: recomputable)
    await refresh_goal_progress(db, node_id)
    # Re-fetch after refresh
    pair = await get_goal(db, user.id, node_id, update_accessed=False)
    node, goal = pair  # type: ignore

    linked_tasks = await get_goal_linked_tasks(db, user.id, node_id)

    resp = GoalWithTasksResponse(
        **_to_response(node, goal).model_dump(),
        linked_tasks=[GoalLinkedTaskResponse(**t) for t in linked_tasks],
    )
    return resp


@router.put("/{node_id}", response_model=GoalResponse)
async def update_goal_endpoint(
    node_id: uuid.UUID,
    body: GoalUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update goal fields."""
    pair = await update_goal(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        status=body.status,
        start_date=body.start_date if body.start_date is not None else ...,
        end_date=body.end_date if body.end_date is not None else ...,
        timeframe_label=body.timeframe_label if body.timeframe_label is not None else ...,
        milestones=body.milestones,
        notes=body.notes if body.notes is not None else ...,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return _to_response(*pair)


@router.post("/{node_id}/refresh-progress", response_model=GoalResponse)
async def refresh_progress_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually refresh goal progress computation.
    Invariant D-03: progress is non-canonical, recomputable.
    """
    pair = await get_goal(db, user.id, node_id, update_accessed=False)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    await refresh_goal_progress(db, node_id)
    pair = await get_goal(db, user.id, node_id, update_accessed=False)
    return _to_response(*pair)  # type: ignore
