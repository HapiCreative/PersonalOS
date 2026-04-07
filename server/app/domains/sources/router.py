"""
Sources domain router (Section 8.3).
Endpoints: POST/GET /api/sources, POST /api/sources/{id}/promote
Layer: Core (capture) + Behavioral (triage/promotion)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import ProcessingStatus, SourceType, TriageStatus
from server.app.domains.sources.schemas import (
    FragmentCreate,
    FragmentListResponse,
    FragmentResponse,
    SourceCreate,
    SourceListResponse,
    SourcePromoteRequest,
    SourcePromoteResponse,
    SourceResponse,
    SourceUpdate,
)
from server.app.domains.sources.service import (
    create_fragment,
    create_source,
    get_source,
    list_fragments,
    list_sources,
    promote_source,
    update_source,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _to_response(node, source) -> SourceResponse:
    return SourceResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        source_type=source.source_type,
        url=source.url,
        author=source.author,
        platform=source.platform,
        published_at=source.published_at,
        captured_at=source.captured_at,
        capture_context=source.capture_context,
        raw_content=source.raw_content,
        canonical_content=source.canonical_content,
        processing_status=source.processing_status,
        triage_status=source.triage_status,
        permanence=source.permanence,
        checksum=source.checksum,
        media_refs=source.media_refs,
        # Phase 10: ai_summary/ai_takeaways/ai_entities removed.
        # Enrichments now live in node_enrichments (Section 4.8).
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source_endpoint(
    body: SourceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture a new source item (Section 6: Stage 1 - capture)."""
    try:
        node, source = await create_source(
            db, user.id, body.title, body.summary,
            body.source_type, body.url, body.author, body.platform,
            body.published_at, body.capture_context, body.raw_content,
            body.permanence,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _to_response(node, source)


@router.get("", response_model=SourceListResponse)
async def list_sources_endpoint(
    processing_status: ProcessingStatus | None = Query(default=None),
    triage_status: TriageStatus | None = Query(default=None),
    source_type: SourceType | None = Query(default=None),
    include_archived: bool = False,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List source items with optional filters.
    Supports the 6 source inbox views: All, Raw, Ready, Promoted, Dismissed, Archived.
    """
    items, total = await list_sources(
        db, user.id, processing_status, triage_status, source_type,
        include_archived, limit, offset,
    )
    return SourceListResponse(
        items=[_to_response(n, s) for n, s in items],
        total=total,
    )


@router.get("/{node_id}", response_model=SourceResponse)
async def get_source_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single source item by node ID."""
    pair = await get_source(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return _to_response(*pair)


@router.put("/{node_id}", response_model=SourceResponse)
async def update_source_endpoint(
    node_id: uuid.UUID,
    body: SourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update source item fields."""
    pair = await update_source(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary,
        source_type=body.source_type,
        url=body.url,
        author=body.author,
        platform=body.platform,
        capture_context=body.capture_context,
        raw_content=body.raw_content,
        canonical_content=body.canonical_content,
        permanence=body.permanence,
        processing_status=body.processing_status,
        triage_status=body.triage_status,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return _to_response(*pair)


@router.post("/{node_id}/promote", response_model=SourcePromoteResponse)
async def promote_source_endpoint(
    node_id: uuid.UUID,
    body: SourcePromoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote a source item to a knowledge entity (KB, Task, or Memory).
    Invariant B-01: Promotion contract.
    """
    try:
        promoted_node_id, edge_id = await promote_source(
            db, user.id, node_id,
            body.target_type, body.title,
            body.memory_type, body.priority,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return SourcePromoteResponse(
        promoted_node_id=promoted_node_id,
        edge_id=edge_id,
        source_node_id=node_id,
        target_type=body.target_type,
    )


# =============================================================================
# Source Fragments
# =============================================================================

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
