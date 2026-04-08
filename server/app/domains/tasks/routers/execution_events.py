"""
Task execution events router (Section 3.7).
Endpoints: POST/GET /api/task-execution-events
Layer: Temporal (execution events)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.tasks.schemas import (
    TaskExecutionEventCreate,
    TaskExecutionEventListResponse,
    TaskExecutionEventResponse,
)
from server.app.temporal.execution_events_service import (
    create_execution_event,
    list_execution_events,
)

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
