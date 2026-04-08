"""
Pydantic schemas for goal CRUD operations (Section 2.4).
Invariant D-03: progress is CACHED DERIVED, non-canonical.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import GoalStatus


class GoalCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    start_date: date | None = None
    end_date: date | None = None
    timeframe_label: str | None = None
    milestones: list[dict] = Field(default_factory=list)
    notes: str | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    status: GoalStatus | None = None
    start_date: date | None = None
    end_date: date | None = None
    timeframe_label: str | None = None
    milestones: list[dict] | None = None
    notes: str | None = None


class GoalResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    status: GoalStatus
    start_date: date | None
    end_date: date | None
    timeframe_label: str | None
    # Invariant D-03: Non-canonical, CACHED DERIVED
    progress: float
    milestones: list[dict]
    notes: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class GoalListResponse(BaseModel):
    items: list[GoalResponse]
    total: int
