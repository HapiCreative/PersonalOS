"""
Node model (Section 2.2) and companion tables.
Invariant S-01: embedding = CACHED DERIVED, last_accessed_at = BEHAVIORAL TRACKING.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import NodeType, InboxItemStatus


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
