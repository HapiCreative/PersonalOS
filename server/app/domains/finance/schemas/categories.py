"""Category schemas for the finance domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    """Create a financial category."""
    name: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None
    icon: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    """Update a financial category."""
    name: str | None = Field(default=None, min_length=1)
    parent_id: uuid.UUID | None = None
    icon: str | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    """Category response."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon: str | None
    is_system: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryTreeResponse(BaseModel):
    """Category with children for hierarchy display."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon: str | None
    is_system: bool
    sort_order: int
    created_at: datetime
    children: list["CategoryTreeResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
