"""
Pydantic schemas for project operations (Section 2.4, TABLE 19).
Projects are lightweight containers grouping goals/tasks via belongs_to edges.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import ProjectStatus


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    status: ProjectStatus | None = None
    description: str | None = None
    tags: list[str] | None = None


class ProjectResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    status: ProjectStatus
    description: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class ProjectLinkedItemResponse(BaseModel):
    """A goal or task linked to a project via belongs_to edge."""
    node_id: uuid.UUID
    title: str
    node_type: str  # 'goal' or 'task'
    status: str
    edge_id: uuid.UUID
    edge_weight: float


class ProjectWithLinksResponse(ProjectResponse):
    """Project response including linked goals and tasks."""
    linked_items: list[ProjectLinkedItemResponse] = Field(default_factory=list)
