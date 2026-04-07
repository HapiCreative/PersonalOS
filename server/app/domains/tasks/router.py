"""
Tasks domain router (Section 8.3).
Endpoints: POST/GET /api/tasks, POST /api/tasks/{id}/transition
Layer: Core (read/write) + Temporal (execution events)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import TaskStatus, TaskPriority, TaskExecutionEventType
from server.app.domains.tasks.schemas import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskTransition,
    TaskUpdate,
    TaskExecutionEventCreate,
    TaskExecutionEventListResponse,
    TaskExecutionEventResponse,
)
from server.app.domains.tasks.service import (
    create_task,
    get_task,
    list_tasks,
    transition_task,
    update_task,
)
from server.app.temporal.execution_events_service import (
    create_execution_event,
    list_execution_events,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _to_response(node, task) -> TaskResponse:
    return TaskResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        recurrence=task.recurrence,
        is_recurring=task.is_recurring,
        notes=task.notes,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task_endpoint(
    body: TaskCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task."""
    try:
        node, task = await create_task(
            db, user.id, body.title, body.summary,
            body.status, body.priority, body.due_date,
            body.recurrence, body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return _to_response(node, task)


@router.get("", response_model=TaskListResponse)
async def list_tasks_endpoint(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    priority: TaskPriority | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tasks with optional filters."""
    items, total = await list_tasks(
        db, user.id, status_filter, priority, include_archived, limit, offset,
    )
    return TaskListResponse(
        items=[_to_response(n, t) for n, t in items],
        total=total,
    )


@router.get("/{node_id}", response_model=TaskResponse)
async def get_task_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single task by node ID."""
    pair = await get_task(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=TaskResponse)
async def update_task_endpoint(
    node_id: uuid.UUID,
    body: TaskUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update task fields."""
    try:
        pair = await update_task(
            db, user.id, node_id,
            title=body.title,
            summary=body.summary,
            priority=body.priority,
            due_date=body.due_date if body.due_date is not None else ...,
            recurrence=body.recurrence if body.recurrence is not None else ...,
            notes=body.notes if body.notes is not None else ...,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_response(*pair)


@router.post("/{node_id}/transition", response_model=TaskResponse)
async def transition_task_endpoint(
    node_id: uuid.UUID,
    body: TaskTransition,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Transition task status with state machine validation.
    Invariant B-03: State machine transitions.
    Invariant S-02: Recurring task + done = invalid.
    """
    try:
        node, task = await transition_task(db, user.id, node_id, body.new_status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return _to_response(node, task)


# =============================================================================
# Task Execution Events (Section 3.7)
# =============================================================================

events_router = APIRouter(prefix="/api/task-execution-events", tags=["task-execution-events"])


@events_router.post("", response_model=TaskExecutionEventResponse, status_code=status.HTTP_201_CREATED)
async def create_execution_event_endpoint(
    body: TaskExecutionEventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a task execution event.
    Invariant S-03: Completion state derivation.
    Invariant S-04: Execution event uniqueness.
    """
    try:
        event = await create_execution_event(
            db, user.id, body.task_id, body.event_type,
            body.expected_for_date, body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TaskExecutionEventResponse.model_validate(event)


@events_router.get("", response_model=TaskExecutionEventListResponse)
async def list_execution_events_endpoint(
    task_id: uuid.UUID | None = None,
    expected_for_date: str | None = None,
    include_deleted: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List task execution events with optional filters."""
    from datetime import date as date_type
    parsed_date = None
    if expected_for_date:
        parsed_date = date_type.fromisoformat(expected_for_date)

    events, total = await list_execution_events(
        db, user.id, task_id, parsed_date, include_deleted, limit, offset,
    )
    return TaskExecutionEventListResponse(
        items=[TaskExecutionEventResponse.model_validate(e) for e in events],
        total=total,
    )
