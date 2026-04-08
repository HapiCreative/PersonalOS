"""Pydantic schemas for inbox domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import InboxItemStatus


class InboxItemCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    title: str | None = None  # auto-generated from raw_text if not provided


class InboxItemUpdate(BaseModel):
    raw_text: str | None = Field(default=None, min_length=1)
    status: InboxItemStatus | None = None
    title: str | None = None


class InboxItemResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    raw_text: str
    status: InboxItemStatus
    promoted_to_node_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class InboxItemListResponse(BaseModel):
    items: list[InboxItemResponse]
    total: int
