"""
Phase 10: Admin/System endpoints for export/import, retention, caching, and batch operations.
Section 8.3: API endpoints (layer-annotated).

Endpoints:
  - POST /api/admin/export — Export all Core entities (JSON)
  - POST /api/admin/import — Import Core entities from JSON
  - POST /api/admin/retention/enforce — Run retention policy cleanup
  - GET  /api/admin/retention/stats — Get retention statistics
  - POST /api/admin/cache/refresh — Refresh materialized views
  - POST /api/admin/batch-embed — Batch embed nodes
"""

import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.db.database import get_db
from server.app.core.auth.dependencies import get_current_user
from server.app.core.models.user import User
from server.app.core.services.export_import import export_all, import_all
from server.app.core.services.retention import (
    enforce_retention_policies,
    get_retention_stats,
)
from server.app.core.services.cache import refresh_materialized_views
from server.app.core.services.batch_embedding import batch_embed_nodes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# Export/Import (Section 1.1: Core entities are exportable)
# =============================================================================


class ExportRequest(BaseModel):
    include_archived: bool = True
    include_enrichments: bool = True


class ImportRequest(BaseModel):
    data: dict
    merge_strategy: str = Field(
        default="skip_existing",
        description="Import strategy: 'skip_existing' or 'create_new'",
    )


@router.post("/export")
async def export_data(
    req: ExportRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Export all Core entities for the current user as JSON.
    Section 1.1: Core entities are exportable.
    Section 1.7: User-owned data — always exportable.
    """
    if req is None:
        req = ExportRequest()

    try:
        data = await export_all(
            db,
            owner_id=user.id,
            include_archived=req.include_archived,
            include_enrichments=req.include_enrichments,
        )
        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": f"attachment; filename=personalos_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            },
        )
    except Exception as e:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")


@router.post("/import")
async def import_data(
    req: ImportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Import Core entities from a JSON export payload.
    Creates new nodes/edges, mapping old IDs to new IDs.
    """
    try:
        result = await import_all(
            db,
            owner_id=user.id,
            data=req.data,
            merge_strategy=req.merge_strategy,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Import failed")
        raise HTTPException(status_code=500, detail=f"Import failed: {e}")


# =============================================================================
# Retention Policy (Section 1.7)
# =============================================================================


@router.post("/retention/enforce")
async def enforce_retention(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Run retention policy enforcement.
    Section 1.7: Retention Defaults.
    - Pipeline jobs: 30-day cleanup for completed/failed
    - Enrichments superseded: 180-day minimum retention
    """
    result = await enforce_retention_policies(db)
    return {
        "pipeline_jobs_deleted": result.pipeline_jobs_deleted,
        "enrichments_deleted": result.enrichments_deleted,
        "errors": result.errors,
    }


@router.get("/retention/stats")
async def retention_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current retention policy statistics."""
    return await get_retention_stats(db)


# =============================================================================
# Caching (Phase 10: materialized view refresh)
# =============================================================================


@router.post("/cache/refresh")
async def refresh_cache(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Refresh materialized views for signal score caching.
    Section 4.1: Signal scores cached in materialized view.
    Invariant D-02: Recomputable from Core data.
    """
    result = await refresh_materialized_views(db)
    return {"materialized_views": result}


# =============================================================================
# Batch Embedding (Phase 10: batch embedding)
# =============================================================================


class BatchEmbedRequest(BaseModel):
    node_ids: list[str] | None = None
    force_recompute: bool = False
    limit: int = Field(default=200, le=1000)


@router.post("/batch-embed")
async def batch_embed(
    req: BatchEmbedRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Batch generate embeddings for nodes.
    Invariant S-01: embedding is CACHED DERIVED — recomputable.
    """
    node_uuids = None
    if req.node_ids:
        try:
            node_uuids = [uuid.UUID(nid) for nid in req.node_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid node ID format")

    result = await batch_embed_nodes(
        db,
        owner_id=user.id,
        node_ids=node_uuids,
        force_recompute=req.force_recompute,
        limit=req.limit,
    )

    return {
        "total_processed": result.total_processed,
        "total_embedded": result.total_embedded,
        "total_skipped": result.total_skipped,
        "total_errors": result.total_errors,
        "node_ids_embedded": result.node_ids_embedded,
    }
