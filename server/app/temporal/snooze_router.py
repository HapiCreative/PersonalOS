"""
Snooze records router (Section 8.3 — Temporal layer).
Endpoints: POST /api/snooze, DELETE /api/snooze

Invariant T-04: Ownership alignment enforced via service layer.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.temporal.snooze_records import (
    create_snooze,
    delete_snooze,
    get_active_snooze,
)

router = APIRouter(prefix="/api/snooze", tags=["snooze"])


class SnoozeCreateRequest(BaseModel):
    node_id: str
    snoozed_until: datetime


class SnoozeDeleteRequest(BaseModel):
    node_id: str


class SnoozeResponse(BaseModel):
    id: str
    node_id: str
    snoozed_until: str
    created_at: str


@router.post("", response_model=SnoozeResponse)
async def create_snooze_record(
    req: SnoozeCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Snooze a node until a given date.
    Layer: Temporal.
    Invariant T-04: Ownership alignment enforced.
    """
    try:
        record = await create_snooze(
            db, user.id, uuid.UUID(req.node_id), req.snoozed_until,
        )
        return SnoozeResponse(
            id=str(record.id),
            node_id=str(record.node_id),
            snoozed_until=record.snoozed_until.isoformat(),
            created_at=record.created_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("")
async def remove_snooze_record(
    req: SnoozeDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove active snooze for a node (un-snooze).
    Layer: Temporal.
    """
    try:
        removed = await delete_snooze(db, user.id, uuid.UUID(req.node_id))
        return {"removed": removed, "node_id": req.node_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{node_id}", response_model=SnoozeResponse | None)
async def get_snooze_for_node(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the active snooze record for a node, if any."""
    record = await get_active_snooze(db, node_id)
    if record is None:
        return None
    return SnoozeResponse(
        id=str(record.id),
        node_id=str(record.node_id),
        snoozed_until=record.snoozed_until.isoformat(),
        created_at=record.created_at.isoformat(),
    )
