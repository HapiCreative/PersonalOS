"""Pydantic schemas for source fragment operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import FragmentType


class FragmentCreate(BaseModel):
    fragment_text: str = Field(min_length=1)
    position: int = 0
    fragment_type: FragmentType = FragmentType.PARAGRAPH
    section_ref: str | None = None


class FragmentResponse(BaseModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    fragment_text: str
    position: int
    fragment_type: FragmentType
    section_ref: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FragmentListResponse(BaseModel):
    items: list[FragmentResponse]
    total: int
