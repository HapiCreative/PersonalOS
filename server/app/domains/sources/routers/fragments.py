"""Source fragment endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.sources.schemas.fragments import (
    FragmentCreate,
    FragmentListResponse,
    FragmentResponse,
)
from server.app.domains.sources.services.fragments import (
    create_fragment,
    list_fragments,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("/{node_id}/fragments", response_model=FragmentListResponse)
async def list_fragments_endpoint(
    node_id: uuid.UUID,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List fragments for a source item."""
    try:
        fragments, total = await list_fragments(db, user.id, node_id, limit, offset)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return FragmentListResponse(
        items=[FragmentResponse.model_validate(f) for f in fragments],
        total=total,
    )


@router.post("/{node_id}/fragments", response_model=FragmentResponse, status_code=status.HTTP_201_CREATED)
async def create_fragment_endpoint(
    node_id: uuid.UUID,
    body: FragmentCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a fragment for a source item."""
    try:
        fragment = await create_fragment(
            db, user.id, node_id,
            body.fragment_text, body.position,
            body.fragment_type, body.section_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return FragmentResponse.model_validate(fragment)
