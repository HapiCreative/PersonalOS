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

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
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


class DailyPlan(Base):
    """
    Section 3 (TABLE 22): daily_plans temporal table.
    One plan per user per date. First commit wins; subsequent edits update in place.

    Invariant T-01: No temporal-to-temporal FKs (references Core users + nodes only).
    Invariant T-04: user_id must match owner_id of referenced task nodes.
    """
    __tablename__ = "daily_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    selected_task_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        default=list,
        comment="Task node IDs chosen for the day (references nodes.id)",
    )
    intention_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional daily intention text",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the plan was closed (evening reflection)",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_plans_user_date"),
        Index("idx_daily_plans_user", "user_id"),
        Index("idx_daily_plans_date", "date"),
    )


class FocusSession(Base):
    """
    Section 3 (TABLE 25): focus_sessions temporal table.
    Timed work sessions linked to a task. Append-only temporal records.

    Invariant T-01: No temporal-to-temporal FKs (references Core nodes only).
    Invariant T-02: Append-only (application layer enforces no deletes).
    Invariant T-04: user_id must match task node's owner_id.
    """
    __tablename__ = "focus_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Task being focused on (FK -> nodes.id)",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="NULL if session still active",
    )
    duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration in seconds, computed when session ends",
    )

    __table_args__ = (
        CheckConstraint("duration IS NULL OR duration >= 0", name="chk_focus_session_duration"),
        Index("idx_focus_sessions_user", "user_id"),
        Index("idx_focus_sessions_task", "task_id"),
        Index("idx_focus_sessions_started", "started_at"),
    )


class SnoozeRecord(Base):
    """
    Section 3.5: snooze_records temporal table.
    Deferred cleanup items — hidden from cleanup queues until snoozed_until.

    Visibility precedence (Section 1.6): archived > snoozed > stale.

    Invariant T-01: No temporal-to-temporal FKs (references Core nodes only).
    Invariant T-04: Ownership alignment (validated at service layer via node ownership).
    """
    __tablename__ = "snooze_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Snoozed entity (FK -> nodes)",
    )
    snoozed_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When to resurface the item in cleanup queues",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint("snoozed_until > created_at", name="snooze_future"),
        Index("idx_snooze_records_node", "node_id"),
        Index("idx_snooze_records_until", "snoozed_until"),
    )
