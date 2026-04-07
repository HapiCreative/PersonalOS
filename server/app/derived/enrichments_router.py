"""
Node enrichments router (Section 4.8 — Derived Layer).
Endpoints for querying and managing enrichments.
Invariant S-05: One active enrichment per type.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import EnrichmentType
from server.app.derived.enrichments import (
    get_enrichments_for_node,
    get_active_enrichment,
    get_enrichment_history,
    rollback_enrichment,
)

router = APIRouter(prefix="/api/enrichments", tags=["enrichments"])


class EnrichmentResponse(BaseModel):
    id: str
    node_id: str
    enrichment_type: str
    payload: dict
    status: str
    prompt_version: str | None = None
    model_version: str | None = None
    superseded_at: str | None = None
    created_at: str
    pipeline_job_id: str | None = None


class EnrichmentListResponse(BaseModel):
    items: list[EnrichmentResponse]
    total: int


class RollbackRequest(BaseModel):
    restore_enrichment_id: str


def _to_response(enrichment) -> EnrichmentResponse:
    return EnrichmentResponse(
        id=str(enrichment.id),
        node_id=str(enrichment.node_id),
        enrichment_type=enrichment.enrichment_type.value,
        payload=enrichment.payload,
        status=enrichment.status.value,
        prompt_version=enrichment.prompt_version,
        model_version=enrichment.model_version,
        superseded_at=enrichment.superseded_at.isoformat() if enrichment.superseded_at else None,
        created_at=enrichment.created_at.isoformat() if enrichment.created_at else "",
        pipeline_job_id=str(enrichment.pipeline_job_id) if enrichment.pipeline_job_id else None,
    )


@router.get("/{node_id}", response_model=EnrichmentListResponse)
async def get_node_enrichments(
    node_id: uuid.UUID,
    include_superseded: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all enrichments for a node. Invariant S-05: active enrichments only by default."""
    enrichments = await get_enrichments_for_node(db, node_id, include_superseded=include_superseded)
    return EnrichmentListResponse(
        items=[_to_response(e) for e in enrichments],
        total=len(enrichments),
    )


@router.get("/{node_id}/{enrichment_type}", response_model=EnrichmentResponse)
async def get_active_node_enrichment(
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the active enrichment for a specific node+type. Invariant S-05."""
    enrichment = await get_active_enrichment(db, node_id, enrichment_type)
    if not enrichment:
        raise HTTPException(status_code=404, detail="No active enrichment found")
    return _to_response(enrichment)


@router.get("/{node_id}/{enrichment_type}/history", response_model=EnrichmentListResponse)
async def get_enrichment_version_history(
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get enrichment version history for a node+type. Newest first."""
    history = await get_enrichment_history(db, node_id, enrichment_type, limit=limit)
    return EnrichmentListResponse(
        items=[_to_response(e) for e in history],
        total=len(history),
    )


@router.post("/{node_id}/{enrichment_type}/rollback", response_model=EnrichmentResponse)
async def rollback_node_enrichment(
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    request: RollbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Rollback to a previous enrichment version.
    Invariant S-05: Supersede current, insert restored copy (immutable history).
    """
    restored = await rollback_enrichment(
        db, node_id, enrichment_type, uuid.UUID(request.restore_enrichment_id)
    )
    if not restored:
        raise HTTPException(status_code=404, detail="Source enrichment not found or type mismatch")
    return _to_response(restored)
