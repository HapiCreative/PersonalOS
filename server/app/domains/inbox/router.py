"""
Inbox domain router (Section 8.3).
Endpoint: POST /api/inbox
Layer: Core (capture)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import InboxItemStatus
from server.app.domains.inbox.schemas import (
    InboxItemCreate,
    InboxItemListResponse,
    InboxItemResponse,
    InboxItemUpdate,
)
from server.app.domains.inbox.service import (
    create_inbox_item,
    get_inbox_item,
    list_inbox_items,
    update_inbox_item,
)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def _to_response(node, inbox_item) -> InboxItemResponse:
    return InboxItemResponse(
        node_id=node.id,
        title=node.title,
        raw_text=inbox_item.raw_text,
        status=inbox_item.status,
        promoted_to_node_id=inbox_item.promoted_to_node_id,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=InboxItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inbox_endpoint(
    body: InboxItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quick capture: creates a Core inbox_item node (Section 5.4)."""
    node, inbox_item = await create_inbox_item(db, user.id, body.raw_text, body.title)
    return _to_response(node, inbox_item)


@router.get("", response_model=InboxItemListResponse)
async def list_inbox_endpoint(
    status_filter: InboxItemStatus | None = Query(default=None, alias="status"),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List inbox items with optional status filter."""
    items, total = await list_inbox_items(db, user.id, status_filter, include_archived, limit, offset)
    return InboxItemListResponse(
        items=[_to_response(n, i) for n, i in items],
        total=total,
    )


@router.get("/{node_id}", response_model=InboxItemResponse)
async def get_inbox_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single inbox item."""
    pair = await get_inbox_item(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbox item not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=InboxItemResponse)
async def update_inbox_endpoint(
    node_id: uuid.UUID,
    body: InboxItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update inbox item fields (raw_text, status, title)."""
    pair = await update_inbox_item(
        db, user.id, node_id,
        raw_text=body.raw_text,
        status=body.status,
        title=body.title,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbox item not found")
    return _to_response(*pair)
