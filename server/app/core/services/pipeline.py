"""
Pipeline jobs service (Section 7.3).
Manages LLM pipeline operations with idempotency, retry, and status tracking.
Invariant B-04: Pipeline jobs inherit ownership from their target node.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import PipelineJob
from server.app.core.models.enums import PipelineJobType, PipelineJobStatus

logger = logging.getLogger(__name__)


async def create_pipeline_job(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_type: PipelineJobType,
    target_node_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    prompt_version: str | None = None,
    model_version: str | None = None,
    input_data: dict | None = None,
    max_retries: int = 3,
) -> PipelineJob:
    """
    Create a new pipeline job.
    Invariant B-04: Pipeline jobs inherit ownership from their target node.
    Idempotency: If idempotency_key is provided and a job already exists, return it.
    """
    # Check idempotency
    if idempotency_key:
        existing = await db.execute(
            select(PipelineJob).where(PipelineJob.idempotency_key == idempotency_key)
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return existing_job

    job = PipelineJob(
        user_id=user_id,
        target_node_id=target_node_id,
        job_type=job_type,
        status=PipelineJobStatus.PENDING,
        idempotency_key=idempotency_key,
        prompt_version=prompt_version,
        model_version=model_version,
        input_data=input_data or {},
        max_retries=max_retries,
    )
    db.add(job)
    await db.flush()
    return job


async def start_job(db: AsyncSession, job_id: uuid.UUID) -> PipelineJob | None:
    """Mark a job as running."""
    result = await db.execute(select(PipelineJob).where(PipelineJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or job.status != PipelineJobStatus.PENDING:
        return None
    job.status = PipelineJobStatus.RUNNING
    job.started_at = datetime.now(timezone.utc)
    await db.flush()
    return job


async def complete_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    output_data: dict | None = None,
) -> PipelineJob | None:
    """Mark a job as completed with output."""
    result = await db.execute(select(PipelineJob).where(PipelineJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or job.status != PipelineJobStatus.RUNNING:
        return None
    job.status = PipelineJobStatus.COMPLETED
    job.output_data = output_data or {}
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return job


async def fail_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    error_message: str,
) -> PipelineJob | None:
    """Mark a job as failed. Increments retry_count. Resets to pending if retries remain."""
    result = await db.execute(select(PipelineJob).where(PipelineJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return None
    job.retry_count += 1
    job.error_message = error_message
    if job.retry_count < job.max_retries:
        # Reset to pending for retry
        job.status = PipelineJobStatus.PENDING
        job.started_at = None
    else:
        job.status = PipelineJobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return job


async def cancel_job(db: AsyncSession, job_id: uuid.UUID) -> PipelineJob | None:
    """Cancel a pending job."""
    result = await db.execute(select(PipelineJob).where(PipelineJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job or job.status not in (PipelineJobStatus.PENDING, PipelineJobStatus.RUNNING):
        return None
    job.status = PipelineJobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return job


async def get_job(db: AsyncSession, job_id: uuid.UUID, user_id: uuid.UUID) -> PipelineJob | None:
    """Get a job by ID with ownership check."""
    result = await db.execute(
        select(PipelineJob).where(
            and_(PipelineJob.id == job_id, PipelineJob.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_type: PipelineJobType | None = None,
    status: PipelineJobStatus | None = None,
    target_node_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PipelineJob], int]:
    """List jobs with filters and ownership enforcement."""
    filters = [PipelineJob.user_id == user_id]
    if job_type:
        filters.append(PipelineJob.job_type == job_type)
    if status:
        filters.append(PipelineJob.status == status)
    if target_node_id:
        filters.append(PipelineJob.target_node_id == target_node_id)

    # Count
    from sqlalchemy import func
    count_stmt = select(func.count()).select_from(PipelineJob).where(*filters)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Fetch
    stmt = (
        select(PipelineJob)
        .where(*filters)
        .order_by(PipelineJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    jobs = list(result.scalars().all())

    return jobs, total


async def get_pending_jobs(
    db: AsyncSession,
    job_type: PipelineJobType | None = None,
    limit: int = 10,
) -> list[PipelineJob]:
    """Get pending jobs ready for processing."""
    filters = [PipelineJob.status == PipelineJobStatus.PENDING]
    if job_type:
        filters.append(PipelineJob.job_type == job_type)

    stmt = (
        select(PipelineJob)
        .where(*filters)
        .order_by(PipelineJob.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
