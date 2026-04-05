"""Pydantic schemas for node operations (Section 2.2)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import NodeType


class NodeCreate(BaseModel):
    type: NodeType
    title: str = Field(min_length=1)
    summary: str | None = None


class NodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None


class NodeResponse(BaseModel):
    id: uuid.UUID
    type: NodeType
    owner_id: uuid.UUID
    title: str
    summary: str | None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class NodeListResponse(BaseModel):
    items: list[NodeResponse]
    total: int
