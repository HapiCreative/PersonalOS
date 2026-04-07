"""
Pipeline jobs router (Section 7.3).
Endpoints for querying pipeline job status.
Invariant B-04: Pipeline jobs inherit ownership from their target node.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import PipelineJobType, PipelineJobStatus
from server.app.core.services.pipeline import get_job, list_jobs, cancel_job

router = APIRouter(prefix="/api/pipeline-jobs", tags=["pipeline"])


class PipelineJobResponse(BaseModel):
    id: str
    user_id: str
    target_node_id: str | None = None
    job_type: str
    status: str
    idempotency_key: str | None = None
    prompt_version: str | None = None
    model_version: str | None = None
    input_data: dict = {}
    output_data: dict = {}
    error_message: str | None = None
    retry_count: int
    max_retries: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None


class PipelineJobListResponse(BaseModel):
    items: list[PipelineJobResponse]
    total: int


def _to_response(job) -> PipelineJobResponse:
    return PipelineJobResponse(
        id=str(job.id),
        user_id=str(job.user_id),
        target_node_id=str(job.target_node_id) if job.target_node_id else None,
        job_type=job.job_type.value,
        status=job.status.value,
        idempotency_key=job.idempotency_key,
        prompt_version=job.prompt_version,
        model_version=job.model_version,
        input_data=job.input_data or {},
        output_data=job.output_data or {},
        error_message=job.error_message,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("", response_model=PipelineJobListResponse)
async def list_pipeline_jobs(
    job_type: PipelineJobType | None = Query(None),
    status_filter: PipelineJobStatus | None = Query(None, alias="status"),
    target_node_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pipeline jobs with filters. Ownership enforced."""
    jobs, total = await list_jobs(
        db, user.id,
        job_type=job_type,
        status=status_filter,
        target_node_id=target_node_id,
        limit=limit,
        offset=offset,
    )
    return PipelineJobListResponse(
        items=[_to_response(j) for j in jobs],
        total=total,
    )


@router.get("/{job_id}", response_model=PipelineJobResponse)
async def get_pipeline_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific pipeline job. Ownership enforced."""
    job = await get_job(db, job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Pipeline job not found")
    return _to_response(job)


@router.post("/{job_id}/cancel", response_model=PipelineJobResponse)
async def cancel_pipeline_job(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending pipeline job."""
    # Verify ownership first
    job = await get_job(db, job_id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Pipeline job not found")

    cancelled = await cancel_job(db, job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job cannot be cancelled (not pending/running)",
        )
    return _to_response(cancelled)
