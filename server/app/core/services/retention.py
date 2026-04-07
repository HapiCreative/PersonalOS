"""
Phase 10: Retention policy enforcement.
Section 1.7: Deletion & Retention Policy.

Retention Defaults:
  - User-owned data: never auto-delete
  - Recomputable data: purge freely
  - Operational/debug data: short retention (30 days)
  - Versioned user-adjacent generated artifacts: medium retention (180+ days)

Specific policies:
  - Pipeline jobs (completed/failed): 30-day cleanup
  - Enrichments (superseded): 180-day minimum retention
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import PipelineJob, NodeEnrichment
from server.app.core.models.enums import PipelineJobStatus, EnrichmentStatus

logger = logging.getLogger(__name__)

# Retention periods (Section 1.7)
PIPELINE_JOB_RETENTION_DAYS = 30
ENRICHMENT_SUPERSEDED_RETENTION_DAYS = 180


@dataclass
class RetentionCleanupResult:
    """Result of a retention cleanup operation."""
    pipeline_jobs_deleted: int
    enrichments_deleted: int
    errors: list[str]


async def enforce_retention_policies(db: AsyncSession) -> RetentionCleanupResult:
    """
    Run all retention policy cleanup tasks.
    Section 1.7: Retention Defaults enforcement.
    """
    errors: list[str] = []

    # 1. Pipeline jobs: 30-day cleanup for completed/failed
    pipeline_deleted = 0
    try:
        pipeline_deleted = await _cleanup_pipeline_jobs(db)
        logger.info("Retention: deleted %d expired pipeline jobs", pipeline_deleted)
    except Exception as e:
        logger.exception("Retention: pipeline job cleanup failed")
        errors.append(f"Pipeline job cleanup failed: {e}")

    # 2. Enrichments superseded: 180-day minimum retention
    enrichments_deleted = 0
    try:
        enrichments_deleted = await _cleanup_superseded_enrichments(db)
        logger.info("Retention: deleted %d expired superseded enrichments", enrichments_deleted)
    except Exception as e:
        logger.exception("Retention: enrichment cleanup failed")
        errors.append(f"Enrichment cleanup failed: {e}")

    return RetentionCleanupResult(
        pipeline_jobs_deleted=pipeline_deleted,
        enrichments_deleted=enrichments_deleted,
        errors=errors,
    )


async def _cleanup_pipeline_jobs(db: AsyncSession) -> int:
    """
    Delete completed/failed pipeline jobs older than 30 days.
    Section 7.3: Pipeline jobs retention.
    Retention: 30-day cleanup for completed/failed.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=PIPELINE_JOB_RETENTION_DAYS)

    # Count first for logging
    count_stmt = select(func.count()).select_from(PipelineJob).where(
        and_(
            PipelineJob.status.in_([
                PipelineJobStatus.COMPLETED,
                PipelineJobStatus.FAILED,
            ]),
            PipelineJob.completed_at.isnot(None),
            PipelineJob.completed_at < cutoff,
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    if total == 0:
        return 0

    # Delete in batches to avoid long transactions
    deleted = 0
    batch_size = 100
    while deleted < total:
        # Find IDs to delete
        id_stmt = (
            select(PipelineJob.id)
            .where(
                and_(
                    PipelineJob.status.in_([
                        PipelineJobStatus.COMPLETED,
                        PipelineJobStatus.FAILED,
                    ]),
                    PipelineJob.completed_at.isnot(None),
                    PipelineJob.completed_at < cutoff,
                )
            )
            .limit(batch_size)
        )
        id_result = await db.execute(id_stmt)
        ids = [row[0] for row in id_result.all()]

        if not ids:
            break

        del_stmt = delete(PipelineJob).where(PipelineJob.id.in_(ids))
        result = await db.execute(del_stmt)
        deleted += result.rowcount
        await db.flush()

    return deleted


async def _cleanup_superseded_enrichments(db: AsyncSession) -> int:
    """
    Delete superseded enrichments older than 180 days.
    Section 4.8: Node enrichments retention.
    Retention: 180+ days minimum for superseded enrichments.

    Only deletes enrichments where:
    - superseded_at IS NOT NULL (not the current active version)
    - superseded_at < 180 days ago
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=ENRICHMENT_SUPERSEDED_RETENTION_DAYS)

    count_stmt = select(func.count()).select_from(NodeEnrichment).where(
        and_(
            NodeEnrichment.superseded_at.isnot(None),
            NodeEnrichment.superseded_at < cutoff,
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    if total == 0:
        return 0

    # Delete in batches
    deleted = 0
    batch_size = 100
    while deleted < total:
        id_stmt = (
            select(NodeEnrichment.id)
            .where(
                and_(
                    NodeEnrichment.superseded_at.isnot(None),
                    NodeEnrichment.superseded_at < cutoff,
                )
            )
            .limit(batch_size)
        )
        id_result = await db.execute(id_stmt)
        ids = [row[0] for row in id_result.all()]

        if not ids:
            break

        del_stmt = delete(NodeEnrichment).where(NodeEnrichment.id.in_(ids))
        result = await db.execute(del_stmt)
        deleted += result.rowcount
        await db.flush()

    return deleted


async def get_retention_stats(db: AsyncSession) -> dict:
    """
    Get current retention statistics for monitoring.
    """
    now = datetime.now(timezone.utc)
    pipeline_cutoff = now - timedelta(days=PIPELINE_JOB_RETENTION_DAYS)
    enrichment_cutoff = now - timedelta(days=ENRICHMENT_SUPERSEDED_RETENTION_DAYS)

    # Pipeline jobs eligible for cleanup
    pipeline_eligible = await db.execute(
        select(func.count()).select_from(PipelineJob).where(
            and_(
                PipelineJob.status.in_([
                    PipelineJobStatus.COMPLETED,
                    PipelineJobStatus.FAILED,
                ]),
                PipelineJob.completed_at.isnot(None),
                PipelineJob.completed_at < pipeline_cutoff,
            )
        )
    )

    # Superseded enrichments eligible for cleanup
    enrichment_eligible = await db.execute(
        select(func.count()).select_from(NodeEnrichment).where(
            and_(
                NodeEnrichment.superseded_at.isnot(None),
                NodeEnrichment.superseded_at < enrichment_cutoff,
            )
        )
    )

    # Total pipeline jobs
    total_pipeline = await db.execute(
        select(func.count()).select_from(PipelineJob)
    )

    # Total enrichments
    total_enrichments = await db.execute(
        select(func.count()).select_from(NodeEnrichment)
    )

    return {
        "pipeline_jobs": {
            "total": total_pipeline.scalar() or 0,
            "eligible_for_cleanup": pipeline_eligible.scalar() or 0,
            "retention_days": PIPELINE_JOB_RETENTION_DAYS,
        },
        "enrichments": {
            "total": total_enrichments.scalar() or 0,
            "superseded_eligible_for_cleanup": enrichment_eligible.scalar() or 0,
            "retention_days": ENRICHMENT_SUPERSEDED_RETENTION_DAYS,
        },
    }
