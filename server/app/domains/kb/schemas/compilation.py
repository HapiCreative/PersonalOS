"""Pydantic schemas for KB compilation pipeline (Section 7)."""

import uuid

from pydantic import BaseModel, Field

from server.app.core.models.enums import CompileStatus, PipelineStage


class KBCompileRequest(BaseModel):
    """Request to trigger or advance the compilation pipeline."""
    action: str = Field(
        description="Pipeline action: 'compile' to start compilation, 'accept' to accept draft, 'reject' to send back to review"
    )


class KBCompileResponse(BaseModel):
    node_id: uuid.UUID
    compile_status: CompileStatus
    pipeline_stage: PipelineStage
    compile_version: int
