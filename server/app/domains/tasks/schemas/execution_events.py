"""Pydantic schemas for task execution events (Section 3.7)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from server.app.core.models.enums import TaskExecutionEventType


class TaskExecutionEventCreate(BaseModel):
    task_id: uuid.UUID
    event_type: TaskExecutionEventType
    expected_for_date: date
    notes: str | None = None


class TaskExecutionEventResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    event_type: TaskExecutionEventType
    expected_for_date: date
    notes: str | None
    created_at: datetime
    node_deleted: bool

    model_config = {"from_attributes": True}


class TaskExecutionEventListResponse(BaseModel):
    items: list[TaskExecutionEventResponse]
    total: int
