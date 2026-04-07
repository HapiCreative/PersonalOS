"""
Node enrichments service (Section 4.8 — Derived Layer).
Versioned enrichment management with Invariant S-05 enforcement.

Invariant S-05: One active enrichment per type.
Only one row per node_id + enrichment_type where superseded_at IS NULL + status=completed.
Re-enrichment: insert new, supersede old.
Rollback: supersede current, insert restored copy (immutable history).
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, NodeEnrichment
from server.app.core.models.enums import EnrichmentType, EnrichmentStatus

logger = logging.getLogger(__name__)


async def get_active_enrichment(
    db: AsyncSession,
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
) -> NodeEnrichment | None:
    """
    Get the current active enrichment for a node+type.
    Invariant S-05: Only one row where superseded_at IS NULL + status=completed.
    """
    result = await db.execute(
        select(NodeEnrichment).where(
            and_(
                NodeEnrichment.node_id == node_id,
                NodeEnrichment.enrichment_type == enrichment_type,
                NodeEnrichment.superseded_at.is_(None),
                NodeEnrichment.status == EnrichmentStatus.COMPLETED,
            )
        )
    )
    return result.scalar_one_or_none()


async def get_enrichments_for_node(
    db: AsyncSession,
    node_id: uuid.UUID,
    include_superseded: bool = False,
) -> list[NodeEnrichment]:
    """Get all enrichments for a node, optionally including historical versions."""
    filters = [NodeEnrichment.node_id == node_id]
    if not include_superseded:
        filters.append(NodeEnrichment.superseded_at.is_(None))
        filters.append(NodeEnrichment.status == EnrichmentStatus.COMPLETED)

    stmt = (
        select(NodeEnrichment)
        .where(*filters)
        .order_by(NodeEnrichment.enrichment_type, NodeEnrichment.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_enrichment(
    db: AsyncSession,
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    payload: dict,
    status: EnrichmentStatus = EnrichmentStatus.PENDING,
    prompt_version: str | None = None,
    model_version: str | None = None,
    pipeline_job_id: uuid.UUID | None = None,
) -> NodeEnrichment:
    """
    Create a new enrichment record.
    If creating a completed enrichment, supersedes the existing active one (S-05).
    """
    # Invariant S-05: If this is a completed enrichment, supersede the existing one
    if status == EnrichmentStatus.COMPLETED:
        await _supersede_active(db, node_id, enrichment_type)

    enrichment = NodeEnrichment(
        node_id=node_id,
        enrichment_type=enrichment_type,
        payload=payload,
        status=status,
        prompt_version=prompt_version,
        model_version=model_version,
        pipeline_job_id=pipeline_job_id,
    )
    db.add(enrichment)
    await db.flush()
    return enrichment


async def complete_enrichment(
    db: AsyncSession,
    enrichment_id: uuid.UUID,
    payload: dict,
) -> NodeEnrichment | None:
    """
    Complete a pending/processing enrichment with the generated payload.
    Invariant S-05: Supersedes any existing active enrichment for same node+type.
    """
    result = await db.execute(
        select(NodeEnrichment).where(NodeEnrichment.id == enrichment_id)
    )
    enrichment = result.scalar_one_or_none()
    if not enrichment:
        return None

    # Invariant S-05: supersede existing active before marking this completed
    await _supersede_active(db, enrichment.node_id, enrichment.enrichment_type)

    enrichment.payload = payload
    enrichment.status = EnrichmentStatus.COMPLETED
    await db.flush()
    return enrichment


async def fail_enrichment(
    db: AsyncSession,
    enrichment_id: uuid.UUID,
    error_info: dict | None = None,
) -> NodeEnrichment | None:
    """Mark an enrichment as failed."""
    result = await db.execute(
        select(NodeEnrichment).where(NodeEnrichment.id == enrichment_id)
    )
    enrichment = result.scalar_one_or_none()
    if not enrichment:
        return None
    enrichment.status = EnrichmentStatus.FAILED
    if error_info:
        enrichment.payload = {**enrichment.payload, "_error": error_info}
    await db.flush()
    return enrichment


async def rollback_enrichment(
    db: AsyncSession,
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    restore_enrichment_id: uuid.UUID,
) -> NodeEnrichment | None:
    """
    Rollback to a previous enrichment version.
    Invariant S-05: Supersede current, insert restored copy (immutable history).
    """
    # Get the enrichment to restore
    result = await db.execute(
        select(NodeEnrichment).where(NodeEnrichment.id == restore_enrichment_id)
    )
    source = result.scalar_one_or_none()
    if not source or source.node_id != node_id or source.enrichment_type != enrichment_type:
        return None

    # Supersede current active
    await _supersede_active(db, node_id, enrichment_type)

    # Insert a copy of the restored version (immutable history — never modify old rows)
    restored = NodeEnrichment(
        node_id=node_id,
        enrichment_type=enrichment_type,
        payload=source.payload,
        status=EnrichmentStatus.COMPLETED,
        prompt_version=source.prompt_version,
        model_version=source.model_version,
    )
    db.add(restored)
    await db.flush()
    return restored


async def _supersede_active(
    db: AsyncSession,
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
) -> None:
    """
    Supersede the current active enrichment for a node+type.
    Invariant S-05: Sets superseded_at on the existing active row.
    """
    result = await db.execute(
        select(NodeEnrichment).where(
            and_(
                NodeEnrichment.node_id == node_id,
                NodeEnrichment.enrichment_type == enrichment_type,
                NodeEnrichment.superseded_at.is_(None),
                NodeEnrichment.status == EnrichmentStatus.COMPLETED,
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.superseded_at = datetime.now(timezone.utc)
        await db.flush()


async def get_enrichment_history(
    db: AsyncSession,
    node_id: uuid.UUID,
    enrichment_type: EnrichmentType,
    limit: int = 10,
) -> list[NodeEnrichment]:
    """Get enrichment version history for a node+type, newest first."""
    stmt = (
        select(NodeEnrichment)
        .where(
            and_(
                NodeEnrichment.node_id == node_id,
                NodeEnrichment.enrichment_type == enrichment_type,
            )
        )
        .order_by(NodeEnrichment.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
