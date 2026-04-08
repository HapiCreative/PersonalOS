"""KB entry CRUD endpoints (Section 8.3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import CompileStatus, PipelineStage
from server.app.domains.kb.schemas import (
    KBCreate,
    KBListResponse,
    KBResponse,
    KBUpdate,
)
from server.app.domains.kb.services import (
    create_kb_entry,
    get_kb_entry,
    list_kb_entries,
    update_kb_entry,
)

router = APIRouter()


def _to_response(node, kb) -> KBResponse:
    return KBResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        content=kb.content,
        raw_content=kb.raw_content,
        compile_status=kb.compile_status,
        pipeline_stage=kb.pipeline_stage,
        tags=kb.tags,
        compile_version=kb.compile_version,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=KBResponse, status_code=status.HTTP_201_CREATED)
async def create_kb_endpoint(
    body: KBCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new KB entry."""
    node, kb = await create_kb_entry(
        db, user.id, body.title, body.summary,
        body.content, body.raw_content, body.tags,
    )
    return _to_response(node, kb)


@router.get("", response_model=KBListResponse)
async def list_kb_endpoint(
    compile_status: CompileStatus | None = Query(default=None),
    pipeline_stage: PipelineStage | None = Query(default=None),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List KB entries with optional compile_status/pipeline_stage filter."""
    items, total = await list_kb_entries(
        db, user.id, compile_status, pipeline_stage, include_archived, limit, offset,
    )
    return KBListResponse(
        items=[_to_response(n, k) for n, k in items],
        total=total,
    )


@router.get("/{node_id}", response_model=KBResponse)
async def get_kb_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single KB entry by node ID."""
    pair = await get_kb_entry(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KB entry not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=KBResponse)
async def update_kb_endpoint(
    node_id: uuid.UUID,
    body: KBUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update KB entry fields."""
    pair = await update_kb_entry(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        content=body.content,
        raw_content=body.raw_content,
        tags=body.tags,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KB entry not found")
    return _to_response(*pair)
