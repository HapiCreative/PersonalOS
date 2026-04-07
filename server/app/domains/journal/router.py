"""
Journal domain router (Section 8.3).
Endpoints: POST/GET /api/journal
Layer: Core (read/write)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import Mood
from server.app.domains.journal.schemas import (
    JournalCreate,
    JournalListResponse,
    JournalResponse,
    JournalUpdate,
)
from server.app.domains.journal.service import (
    create_journal_entry,
    get_journal_entry,
    list_journal_entries,
    update_journal_entry,
)

router = APIRouter(prefix="/api/journal", tags=["journal"])


def _to_response(node, journal) -> JournalResponse:
    return JournalResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        content=journal.content,
        entry_date=journal.entry_date,
        mood=journal.mood,
        tags=journal.tags or [],
        word_count=journal.word_count,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=JournalResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_endpoint(
    body: JournalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new journal entry."""
    node, journal = await create_journal_entry(
        db, user.id, body.title, body.summary,
        body.content, body.entry_date, body.mood, body.tags,
    )
    return _to_response(node, journal)


@router.get("", response_model=JournalListResponse)
async def list_journal_endpoint(
    mood: Mood | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List journal entries with optional mood filter."""
    items, total = await list_journal_entries(
        db, user.id, mood, include_archived, limit, offset,
    )
    return JournalListResponse(
        items=[_to_response(n, j) for n, j in items],
        total=total,
    )


@router.get("/{node_id}", response_model=JournalResponse)
async def get_journal_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single journal entry by node ID."""
    pair = await get_journal_entry(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=JournalResponse)
async def update_journal_endpoint(
    node_id: uuid.UUID,
    body: JournalUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update journal entry fields."""
    pair = await update_journal_entry(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        content=body.content,
        mood=body.mood if body.mood is not None else ...,
        tags=body.tags if body.tags is not None else ...,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return _to_response(*pair)
