"""
Search router (Section 8.3).
Endpoint: GET /api/search?q=&mode=
Layer: Derived (retrieval)
Phase 1: Full-text only. Phase 3: Hybrid search with embeddings.
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
    mode: str | None = Query(
        default=None,
        description="Search mode: 'fulltext', 'vector', 'hybrid'. Default is fulltext.",
    ),
    limit: int = Query(default=20, le=50),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search across nodes.
    Phase 1: full-text search on title + summary.
    Phase 3: hybrid search combining full-text + vector similarity.
    Ownership enforced at query layer (Section 8.2).
    """
    if mode and mode not in ("fulltext", "vector", "hybrid"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search mode: {mode}. Must be fulltext, vector, or hybrid.",
        )

    nodes, total = await search_nodes(
        db, user.id, q, type, limit, offset, include_archived, mode,
    )
    return SearchResponse(
        items=[NodeResponse.model_validate(n) for n in nodes],
        total=total,
        query=q,
    )
