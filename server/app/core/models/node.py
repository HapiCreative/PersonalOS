"""
Node model (Section 2.2) and companion tables.
Invariant S-01: embedding = CACHED DERIVED, last_accessed_at = BEHAVIORAL TRACKING.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import (
    NodeType, InboxItemStatus, TaskStatus, TaskPriority, Mood,
    SourceType, ProcessingStatus, TriageStatus, Permanence, FragmentType,
    CompileStatus, PipelineStage, MemoryType,
)


class Node(Base):
    """
    Section 2.2: Thin cross-domain shell providing identity, search surface,
    and graph participation.
    """
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[NodeType] = mapped_column(nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Invariant S-01: CACHED DERIVED - semantic embedding, recomputable
    embedding = mapped_column(Vector(1536), nullable=True, comment="CACHED DERIVED: Semantic embedding, recomputable. Invariant S-01.")

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Invariant S-01: BEHAVIORAL TRACKING - last viewed, for decay detection
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="BEHAVIORAL TRACKING: Last viewed for decay detection. Invariant S-01."
    )
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_nodes_type", "type"),
        Index("idx_nodes_owner", "owner_id"),
        Index("idx_nodes_archived", "archived_at", postgresql_where="archived_at IS NULL"),
    )


class InboxItem(Base):
    """Section 2.4: inbox_items companion table."""
    __tablename__ = "inbox_items"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[InboxItemStatus] = mapped_column(nullable=False, default=InboxItemStatus.PENDING)
    promoted_to_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_inbox_items_status", "status"),
    )


class TaskNode(Base):
    """
    Section 2.4: task_nodes companion table.
    Invariant S-02: recurring + done = invalid (CHECK constraint).
    """
    __tablename__ = "task_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[TaskStatus] = mapped_column(nullable=False, default=TaskStatus.TODO)
    priority: Mapped[TaskPriority] = mapped_column(nullable=False, default=TaskPriority.MEDIUM)
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    recurrence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Invariant S-01: CACHED DERIVED - convenience flag derived from recurrence IS NOT NULL
    is_recurring: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="CACHED DERIVED: Convenience flag, derived from recurrence IS NOT NULL. Invariant S-01."
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "NOT (recurrence IS NOT NULL AND status = 'done')",
            name="task_recurring_done_invalid",
        ),
        Index("idx_task_nodes_status_due", "status", "due_date"),
        Index("idx_task_nodes_priority", "priority"),
    )


class JournalNode(Base):
    """
    Section 2.4: journal_nodes companion table.
    v6 change: mood changed from free TEXT to ENUM.
    """
    __tablename__ = "journal_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entry_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    mood: Mapped[Mood | None] = mapped_column(nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    # Invariant S-01: CACHED DERIVED - computed from content length
    word_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Computed from content length. Invariant S-01."
    )

    __table_args__ = (
        Index("idx_journal_nodes_entry_date", "entry_date"),
        Index("idx_journal_nodes_mood", "mood"),
    )


# =============================================================================
# Phase 3: Sources + KB + Memory companion tables
# =============================================================================


class SourceItemNode(Base):
    """
    Section 2.4 / Section 6: source_item_nodes companion table.
    Source items represent external content captured into the system.
    4-stage pipeline: capture -> normalize -> enrich -> promote.
    Invariant B-01: Promotion contract governs source-to-knowledge flow.
    """
    __tablename__ = "source_item_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Source identification
    source_type: Mapped[SourceType] = mapped_column(nullable=False, default=SourceType.OTHER)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Capture metadata
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    capture_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Content
    raw_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    canonical_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline status
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        nullable=False, default=ProcessingStatus.RAW
    )
    triage_status: Mapped[TriageStatus] = mapped_column(
        nullable=False, default=TriageStatus.UNREVIEWED
    )
    permanence: Mapped[Permanence] = mapped_column(
        nullable=False, default=Permanence.REFERENCE
    )

    # Deduplication
    checksum: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Media references
    media_refs: Mapped[dict] = mapped_column(JSONB, default=list)

    # Invariant S-01: CACHED DERIVED - AI enrichment flat fields (temporary bridge for P9 migration)
    ai_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="CACHED DERIVED: AI-generated summary. Temporary bridge, migrate to node_enrichments in P9. Invariant S-01."
    )
    ai_takeaways: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="CACHED DERIVED: AI-generated takeaways. Temporary bridge, migrate to node_enrichments in P9. Invariant S-01."
    )
    ai_entities: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="CACHED DERIVED: AI-extracted entities. Temporary bridge, migrate to node_enrichments in P9. Invariant S-01."
    )

    __table_args__ = (
        Index("idx_source_item_nodes_processing", "processing_status"),
        Index("idx_source_item_nodes_triage", "triage_status"),
        Index("idx_source_item_nodes_type", "source_type"),
        Index("idx_source_item_nodes_checksum", "checksum", postgresql_where="checksum IS NOT NULL"),
        Index("idx_source_item_nodes_url", "url", postgresql_where="url IS NOT NULL"),
        Index("idx_source_item_nodes_captured", "captured_at"),
    )


class SourceFragment(Base):
    """
    Section 6: source_fragments table.
    Fragments are sub-parts of a source item used for fine-grained retrieval and citation.
    """
    __tablename__ = "source_fragments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    fragment_text: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fragment_type: Mapped[FragmentType] = mapped_column(nullable=False, default=FragmentType.PARAGRAPH)
    section_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Invariant S-01: CACHED DERIVED - semantic embedding for fragment-level retrieval
    embedding = mapped_column(
        Vector(1536), nullable=True,
        comment="CACHED DERIVED: Semantic embedding for fragment-level retrieval. Invariant S-01."
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_source_fragments_source", "source_node_id"),
        Index("idx_source_fragments_type", "fragment_type"),
        Index("idx_source_fragments_position", "source_node_id", "position"),
    )


class KBNode(Base):
    """
    Section 2.4: kb_nodes companion table.
    Knowledge base entries are canonical, curated knowledge articles.
    6-stage compilation pipeline: ingest -> parse -> compile -> review -> accept -> stale.
    """
    __tablename__ = "kb_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    compile_status: Mapped[CompileStatus] = mapped_column(
        nullable=False, default=CompileStatus.INGEST
    )
    pipeline_stage: Mapped[PipelineStage] = mapped_column(
        nullable=False, default=PipelineStage.DRAFT
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    compile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("idx_kb_nodes_compile_status", "compile_status"),
        Index("idx_kb_nodes_pipeline_stage", "pipeline_stage"),
    )


class MemoryNode(Base):
    """
    Section 2.4: memory_nodes companion table.
    Captures decisions, insights, lessons, principles, and preferences.
    """
    __tablename__ = "memory_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    memory_type: Mapped[MemoryType] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    __table_args__ = (
        Index("idx_memory_nodes_type", "memory_type"),
        Index("idx_memory_nodes_review", "review_at", postgresql_where="review_at IS NOT NULL"),
    )
