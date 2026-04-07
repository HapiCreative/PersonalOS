"""
Temporal layer models (Section 3).
Temporal records are append-heavy, date-indexed, and never participate in the graph.

Invariants:
- T-01: No temporal-to-temporal FKs
- T-02: Append-only event records
- T-03: Temporal retention (never auto-deleted, flagged on node hard-delete)
- T-04: Ownership alignment
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import TaskExecutionEventType


class TaskExecutionEvent(Base):
    """
    Section 3.7: task_execution_events temporal table.
    Unified execution log for all tasks (recurring and non-recurring).

    Invariant S-04: At most one terminal execution event per task per expected_for_date.
    Invariant T-01: No temporal-to-temporal FKs (references Core task via node_id only).
    Invariant T-02: Append-only (application layer enforces no updates).
    Invariant T-04: user_id must match task node's owner_id.
    """
    __tablename__ = "task_execution_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[TaskExecutionEventType] = mapped_column(nullable=False)
    expected_for_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    # Invariant B-02 / T-03: Flag for when referenced node is hard-deleted
    node_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        # Invariant S-04: unique constraint on task_id + expected_for_date (for non-deleted events)
        Index(
            "idx_task_execution_events_unique",
            "task_id", "expected_for_date",
            unique=True,
            postgresql_where="node_deleted = FALSE",
        ),
        Index("idx_task_execution_events_task", "task_id"),
        Index("idx_task_execution_events_date", "expected_for_date"),
        Index("idx_task_execution_events_user", "user_id"),
    )
