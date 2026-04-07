"""Pydantic schemas for template operations (Section 2.4)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import TemplateTargetType


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1)
    target_type: TemplateTargetType
    structure: dict = Field(default_factory=dict)
    is_system: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    structure: dict | None = None


class TemplateResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    target_type: TemplateTargetType
    structure: dict
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int
