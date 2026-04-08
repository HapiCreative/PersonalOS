"""
Finance Phase F2 — Obligation Nodes & Breakdowns.

F2.6: Core obligation entities with companion table pattern, versioned breakdowns.
Ref: Obligations Addendum Sections 1, 2, 5.1, 7, 8.1.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey,
    Index, Integer, Numeric, SmallInteger, Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import (
    AmountModel,
    BreakdownAmountModel,
    BreakdownComponentType,
    BreakdownStatus,
    ObligationOrigin,
    ObligationStatus,
    ObligationType,
)


class ObligationNode(Base):
    """
    Obligations Addendum Section 2: obligation_nodes companion table.
    Core entity — durable, user-owned recurring financial commitments.
    1:1 with nodes table (node type 'obligation').

    Invariant F-17: amount_model consistency (CHECK constraint).
    Invariant F-18: status lifecycle — cancelled requires ended_at (CHECK constraint).
    Invariant F-19: next_expected_date is CACHED DERIVED (S-01).
    """
    __tablename__ = "obligation_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    obligation_type: Mapped[ObligationType] = mapped_column(nullable=False)
    recurrence_rule: Mapped[str] = mapped_column(Text, nullable=False)
    amount_model: Mapped[AmountModel] = mapped_column(nullable=False)

    # Invariant F-17: fixed -> expected_amount required, ranges null;
    # variable/seasonal -> ranges required
    expected_amount = mapped_column(Numeric(15, 2), nullable=True)
    amount_range_low = mapped_column(Numeric(15, 2), nullable=True)
    amount_range_high = mapped_column(Numeric(15, 2), nullable=True)

    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    counterparty_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK deferred to F3 (counterparty_entities).",
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    billing_anchor: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True,
        comment="Typical day-of-month hint. Not source of truth.",
    )

    # Invariant F-19 + S-01: CACHED DERIVED from recurrence_rule + last obligation_event
    next_expected_date: Mapped[datetime | None] = mapped_column(
        Date, nullable=True,
        comment="CACHED DERIVED: Computed from recurrence_rule + last obligation_event. Invariants S-01, F-19.",
    )

    status: Mapped[ObligationStatus] = mapped_column(
        nullable=False, default=ObligationStatus.ACTIVE,
    )
    autopay: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    origin: Mapped[ObligationOrigin] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Detection confidence at creation. NULL for manual.",
    )
    started_at: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    cancellation_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # Invariant F-17: Amount model consistency
        CheckConstraint(
            "(amount_model = 'fixed' AND expected_amount IS NOT NULL "
            "AND amount_range_low IS NULL AND amount_range_high IS NULL) "
            "OR (amount_model IN ('variable', 'seasonal') "
            "AND amount_range_low IS NOT NULL AND amount_range_high IS NOT NULL)",
            name="obligation_amount_model_consistency",
        ),
        # Invariant F-18: Status lifecycle
        CheckConstraint(
            "(status = 'cancelled' AND ended_at IS NOT NULL) "
            "OR (status = 'active' AND ended_at IS NULL) "
            "OR (status = 'paused')",
            name="obligation_status_lifecycle",
        ),
        Index("idx_obligation_nodes_status", "status"),
        Index("idx_obligation_nodes_account", "account_id"),
        Index("idx_obligation_nodes_category", "category_id",
              postgresql_where="category_id IS NOT NULL"),
        Index("idx_obligation_nodes_next_date", "next_expected_date",
              postgresql_where="next_expected_date IS NOT NULL"),
    )


class ObligationBreakdown(Base):
    """
    Obligations Addendum Section 2: obligation_breakdowns table.
    Sub-components of obligations (e.g. base charge, usage, taxes).
    Versioned via effective_from/effective_to — never mutated for rate changes.

    Invariant F-20: percentage model -> percentage_value required, expected_amount null.
    Invariant F-21: partial unique on (obligation_id, normalized_name) WHERE effective_to IS NULL.
    Invariant F-22: deprecated status requires effective_to set.
    """
    __tablename__ = "obligation_breakdowns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    obligation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    component_type: Mapped[BreakdownComponentType] = mapped_column(nullable=False)
    amount_model: Mapped[BreakdownAmountModel] = mapped_column(nullable=False)

    # Invariant F-20: percentage -> percentage_value non-null, expected_amount null; others inverse
    expected_amount = mapped_column(Numeric(15, 2), nullable=True)
    amount_range_low = mapped_column(Numeric(15, 2), nullable=True)
    amount_range_high = mapped_column(Numeric(15, 2), nullable=True)
    percentage_value = mapped_column(
        Numeric(7, 4), nullable=True,
        comment="For percentage-based: the rate (e.g. 0.0825 for 8.25%). NULL for non-percentage.",
    )

    match_keywords: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True,
        comment="Hints for auto-matching transaction line items.",
    )
    effective_from: Mapped[datetime] = mapped_column(Date, nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(
        Date, nullable=True,
        comment="When superseded. NULL = current version.",
    )
    status: Mapped[BreakdownStatus] = mapped_column(
        nullable=False, default=BreakdownStatus.ACTIVE,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        # Invariant F-20: Breakdown amount model consistency
        CheckConstraint(
            "(amount_model = 'percentage' AND percentage_value IS NOT NULL "
            "AND expected_amount IS NULL) "
            "OR (amount_model IN ('fixed', 'variable', 'seasonal') "
            "AND percentage_value IS NULL)",
            name="breakdown_amount_model_consistency",
        ),
        # Invariant F-22: deprecated status requires effective_to
        CheckConstraint(
            "(status = 'deprecated' AND effective_to IS NOT NULL) "
            "OR (status = 'active')",
            name="breakdown_deprecated_has_end_date",
        ),
        # Invariant F-21: One active version per (obligation_id, normalized_name)
        Index(
            "uq_breakdown_active_version",
            "obligation_id", "normalized_name",
            unique=True,
            postgresql_where="effective_to IS NULL",
        ),
        # Section 7: Obligation breakdown indexes
        Index("idx_breakdown_obligation", "obligation_id"),
        Index("idx_breakdown_component_type", "component_type"),
        Index("idx_breakdown_effective_range", "effective_from", "effective_to"),
    )
