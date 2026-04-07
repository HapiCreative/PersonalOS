"""Pydantic schemas for edge operations (Section 2.3)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import EdgeRelationType, EdgeOrigin, EdgeState


class EdgeCreate(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: EdgeRelationType
    origin: EdgeOrigin = EdgeOrigin.USER
    state: EdgeState = EdgeState.ACTIVE
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)


class EdgeResponse(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    target_id: uuid.UUID
    relation_type: EdgeRelationType
    origin: EdgeOrigin
    state: EdgeState
    weight: float
    confidence: float | None
    metadata: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class EdgeStateUpdate(BaseModel):
    """Phase 5: Update edge state (accept/dismiss suggested links)."""
    state: EdgeState


class EdgeListResponse(BaseModel):
    items: list[EdgeResponse]
    total: int
