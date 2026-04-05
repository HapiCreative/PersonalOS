"""
Edge model (Section 2.3).
Invariants: G-01 (type-pair constraints), G-02 (semantic_reference specificity),
G-03 (same-owner), G-04 (deletion cascade via FK ON DELETE CASCADE).
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, CheckConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import EdgeRelationType, EdgeOrigin, EdgeState


class Edge(Base):
    """Section 2.3: Edges table with full relation taxonomy."""
    __tablename__ = "edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[EdgeRelationType] = mapped_column(nullable=False)
    origin: Mapped[EdgeOrigin] = mapped_column(nullable=False, default=EdgeOrigin.USER)
    state: Mapped[EdgeState] = mapped_column(nullable=False, default=EdgeState.ACTIVE)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Derived: LLM confidence, null for user-created edges."
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("weight >= 0.0 AND weight <= 1.0", name="edges_weight_range"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="edges_confidence_range",
        ),
        Index("idx_edges_source_relation", "source_id", "relation_type"),
        Index("idx_edges_target_relation", "target_id", "relation_type"),
    )
