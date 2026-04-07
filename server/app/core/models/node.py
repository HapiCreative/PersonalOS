"""
Node model (Section 2.2) and companion tables.
Invariant S-01: embedding = CACHED DERIVED, last_accessed_at = BEHAVIORAL TRACKING.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Text, Index
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import (
    NodeType, InboxItemStatus, TaskStatus, TaskPriority, Mood,
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
