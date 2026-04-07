"""Pydantic schemas for memory operations (Section 2.4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import MemoryType


class MemoryCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    memory_type: MemoryType
    content: str = ""
    context: str | None = None
    review_at: datetime | None = None
    tags: list[str] = []


class MemoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    content: str | None = None
    context: str | None = None
    review_at: datetime | None = None
    tags: list[str] | None = None


class MemoryResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    memory_type: MemoryType
    content: str
    context: str | None
    review_at: datetime | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    items: list[MemoryResponse]
    total: int
