"""
Search router (Section 8.3).
Endpoint: GET /api/search?q=
Layer: Derived (retrieval) — Phase 1 uses full-text only, no embeddings.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.schemas.node import NodeResponse
from server.app.core.schemas.search import SearchResponse
from server.app.core.services.search import search_nodes

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=SearchResponse)
async def search_endpoint(
    q: str = Query(min_length=1),
    type: str | None = None,
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full-text search across nodes (title + summary).
    Ownership enforced at query layer (Section 8.2).
    Phase 1: full-text only. Phase 3 adds hybrid search with embeddings.
    """
    nodes, total = await search_nodes(db, user.id, q, type, limit, offset, include_archived)
    return SearchResponse(
        items=[NodeResponse.model_validate(n) for n in nodes],
        total=total,
        query=q,
    )
