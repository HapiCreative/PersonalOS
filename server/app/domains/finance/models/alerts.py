"""
Finance Phase F2 — Finance Alerts Engine.

F2.4: Behavioral alerts table with dedup, lifecycle, and severity.
Ref: Finance Design Rev 3 Section 5.1 + Obligations Addendum Section 5.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import AlertSeverity, AlertStatus, AlertType


class FinanceAlert(Base):
    """
    Section 5.1: finance_alerts table.
    Stateful projection of Derived signals — NOT source of truth (F-15).
    Invariant F-14: dedup via dedup_key before upsert.
    """
    __tablename__ = "finance_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_type: Mapped[AlertType] = mapped_column(nullable=False)
    severity: Mapped[AlertSeverity] = mapped_column(nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        nullable=False, default=AlertStatus.ACTIVE,
    )
    entity_refs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="References: { account_id?, transaction_id?, goal_id?, category_id?, obligation_id? }",
    )
    # Invariant F-14: dedup_key prevents duplicate alerts for same signal
    dedup_key: Mapped[str] = mapped_column(Text, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    explanation: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="DerivedExplanation snapshot.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        # Invariant F-14: unique dedup_key per user prevents duplicate alerts
        Index("uq_finance_alerts_dedup", "user_id", "dedup_key", unique=True),
        Index("idx_finance_alerts_user_status", "user_id", "status"),
        Index("idx_finance_alerts_type", "alert_type"),
        Index("idx_finance_alerts_severity", "severity"),
        Index(
            "idx_finance_alerts_snoozed",
            "snoozed_until",
            postgresql_where="snoozed_until IS NOT NULL",
        ),
    )
