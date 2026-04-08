"""Pydantic schemas for KB entry operations (Section 2.4, Section 7)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import CompileStatus, PipelineStage


class KBCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    content: str = ""
    raw_content: str | None = None
    tags: list[str] = []


class KBUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    content: str | None = None
    raw_content: str | None = None
    tags: list[str] | None = None


class KBResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    content: str
    raw_content: str | None
    compile_status: CompileStatus
    pipeline_stage: PipelineStage
    tags: list[str]
    compile_version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class KBListResponse(BaseModel):
    items: list[KBResponse]
    total: int
