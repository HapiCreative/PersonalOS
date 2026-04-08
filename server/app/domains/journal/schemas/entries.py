"""Pydantic schemas for journal operations (Section 2.4)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import Mood


class JournalCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    content: str = ""
    entry_date: date | None = None  # Defaults to today
    mood: Mood | None = None
    tags: list[str] = Field(default_factory=list)


class JournalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    content: str | None = None
    mood: Mood | None = None
    tags: list[str] | None = None


class JournalResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    content: str
    entry_date: date
    mood: Mood | None
    tags: list[str]
    word_count: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class JournalListResponse(BaseModel):
    items: list[JournalResponse]
    total: int
