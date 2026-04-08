"""Pydantic schemas for goal-linked task responses."""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from server.app.domains.goals.schemas.goals import GoalResponse


class GoalLinkedTaskResponse(BaseModel):
    """A task linked to a goal via goal_tracks_task edge."""
    node_id: uuid.UUID
    title: str
    status: str
    priority: str
    due_date: date | None
    is_recurring: bool
    edge_id: uuid.UUID
    edge_weight: float


class GoalWithTasksResponse(GoalResponse):
    """Goal response including linked tasks."""
    linked_tasks: list[GoalLinkedTaskResponse] = Field(default_factory=list)
