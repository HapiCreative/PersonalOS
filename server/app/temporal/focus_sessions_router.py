"""
Focus sessions router (Section 8.3 — Temporal layer).
Endpoints: GET /api/focus-sessions, POST /api/focus-sessions

Invariant T-02: Append-only (no DELETE endpoints).
Invariant T-04: Ownership alignment enforced via service layer.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.temporal.focus_sessions_service import (
    start_focus_session,
    end_focus_session,
    get_active_focus_session,
    get_focus_session,
    list_focus_sessions,
)

router = APIRouter(prefix="/api/focus-sessions", tags=["focus-sessions"])


class FocusSessionStartRequest(BaseModel):
    task_id: str


class FocusSessionResponse(BaseModel):
    id: str
    user_id: str
    task_id: str
    started_at: str
    ended_at: str | None
    duration: int | None  # seconds


class FocusSessionListResponse(BaseModel):
    items: list[FocusSessionResponse]
    total: int


def _session_to_response(session) -> FocusSessionResponse:
    return FocusSessionResponse(
        id=str(session.id),
        user_id=str(session.user_id),
        task_id=str(session.task_id),
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None,
        duration=session.duration,
    )


@router.post("", response_model=FocusSessionResponse)
async def start_session(
    req: FocusSessionStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a new focus session for a task.
    Automatically ends any existing active session.
    Layer: Temporal.
    Invariant T-04: Ownership alignment enforced.
    """
    try:
        session = await start_focus_session(
            db, user.id, uuid.UUID(req.task_id),
        )
        return _session_to_response(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{session_id}/end", response_model=FocusSessionResponse)
async def end_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End an active focus session. Computes duration."""
    session = await end_focus_session(db, user.id, session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Active session not found or already ended",
        )
    return _session_to_response(session)


@router.get("/active", response_model=FocusSessionResponse | None)
async def get_active(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the currently active focus session, if any."""
    session = await get_active_focus_session(db, user.id)
    if session is None:
        return None
    return _session_to_response(session)


@router.get("", response_model=FocusSessionListResponse)
async def list_sessions(
    task_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List focus sessions, most recent first. Optionally filter by task_id."""
    tid = uuid.UUID(task_id) if task_id else None
    sessions, total = await list_focus_sessions(db, user.id, tid, limit, offset)
    return FocusSessionListResponse(
        items=[_session_to_response(s) for s in sessions],
        total=total,
    )


@router.get("/{session_id}", response_model=FocusSessionResponse)
async def get_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific focus session by ID."""
    session = await get_focus_session(db, user.id, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Focus session not found")
    return _session_to_response(session)
