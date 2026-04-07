"""
Memory domain router (Section 8.3).
Endpoints: POST/GET /api/memory
Layer: Core (read/write)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import MemoryType
from server.app.domains.memory.schemas import (
    MemoryCreate,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdate,
)
from server.app.domains.memory.service import (
    create_memory,
    get_memory,
    list_memories,
    update_memory,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _to_response(node, memory) -> MemoryResponse:
    return MemoryResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        memory_type=memory.memory_type,
        content=memory.content,
        context=memory.context,
        review_at=memory.review_at,
        tags=memory.tags,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_memory_endpoint(
    body: MemoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new memory node."""
    node, memory = await create_memory(
        db, user.id, body.title, body.memory_type,
        body.summary, body.content, body.context,
        body.review_at, body.tags,
    )
    return _to_response(node, memory)


@router.get("", response_model=MemoryListResponse)
async def list_memory_endpoint(
    memory_type: MemoryType | None = Query(default=None),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List memory nodes with optional type filter."""
    items, total = await list_memories(
        db, user.id, memory_type, include_archived, limit, offset,
    )
    return MemoryListResponse(
        items=[_to_response(n, m) for n, m in items],
        total=total,
    )


@router.get("/{node_id}", response_model=MemoryResponse)
async def get_memory_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single memory node by node ID."""
    pair = await get_memory(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=MemoryResponse)
async def update_memory_endpoint(
    node_id: uuid.UUID,
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update memory node fields."""
    pair = await update_memory(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        content=body.content,
        context=body.context,
        review_at=body.review_at if body.review_at is not None else ...,
        tags=body.tags,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return _to_response(*pair)
