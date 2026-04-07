"""Pydantic schemas for task operations (Section 2.4, 3.7)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import (
    TaskStatus, TaskPriority, Mood, TaskExecutionEventType,
)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    recurrence: str | None = None
    notes: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    recurrence: str | None = None
    notes: str | None = None


class TaskTransition(BaseModel):
    """Invariant B-03: State machine transition request."""
    new_status: TaskStatus


class TaskResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None
    recurrence: str | None
    is_recurring: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int


# Task Execution Events (Section 3.7)

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
