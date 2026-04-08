"""Pydantic schemas for source item operations (Section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import (
    Permanence, ProcessingStatus, SourceType, TriageStatus,
)


class SourceCreate(BaseModel):
    title: str = Field(min_length=1)
    summary: str | None = None
    source_type: SourceType = SourceType.OTHER
    url: str | None = None
    author: str | None = None
    platform: str | None = None
    published_at: datetime | None = None
    capture_context: str | None = None
    raw_content: str = ""
    permanence: Permanence = Permanence.REFERENCE


class SourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    source_type: SourceType | None = None
    url: str | None = None
    author: str | None = None
    platform: str | None = None
    capture_context: str | None = None
    raw_content: str | None = None
    canonical_content: str | None = None
    permanence: Permanence | None = None
    processing_status: ProcessingStatus | None = None
    triage_status: TriageStatus | None = None


class SourceResponse(BaseModel):
    node_id: uuid.UUID
    title: str
    summary: str | None
    source_type: SourceType
    url: str | None
    author: str | None
    platform: str | None
    published_at: datetime | None
    captured_at: datetime
    capture_context: str | None
    raw_content: str
    canonical_content: str | None
    processing_status: ProcessingStatus
    triage_status: TriageStatus
    permanence: Permanence
    checksum: str | None
    media_refs: list | dict | None
    # Phase 10: ai_summary, ai_takeaways, ai_entities removed.
    # Enrichments now live exclusively in node_enrichments table (Section 4.8).
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
    total: int


class SourcePromoteRequest(BaseModel):
    """
    Invariant B-01: Promotion contract.
    Specify what to promote the source to (kb_entry, task, or memory).
    """
    target_type: str = Field(
        description="Target node type: 'kb_entry', 'task', or 'memory'"
    )
    title: str | None = None  # Override title for the promoted node
    # For memory promotion
    memory_type: str | None = None
    # For task promotion
    priority: str | None = None


class SourcePromoteResponse(BaseModel):
    """Response after promoting a source item."""
    promoted_node_id: uuid.UUID
    edge_id: uuid.UUID
    source_node_id: uuid.UUID
    target_type: str
