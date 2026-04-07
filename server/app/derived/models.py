"""
Derived layer models (Section 4).
Derived tables store non-canonical, recomputable data for display and ranking.

Invariants:
- D-02: All derived data is fully recomputable from Core + Temporal data.
- D-03: Derived data is non-canonical — never treated as source of truth.
"""

import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, DateTime, Text, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base


class SignalScore(Base):
    """
    Section 4: Signal score cache table.
    5-factor composite score for ranking and relevance.

    Invariant D-02: Fully recomputable from Core (nodes, edges) + Temporal data.
    Invariant D-03: Non-canonical — NOT on the canonical node table.

    Factors and weights:
    - recency: 0.3 (based on updated_at)
    - link_density: 0.25 (based on edge count)
    - completion_state: 0.2 (based on task/goal status)
    - reference_frequency: 0.15 (based on incoming edge count)
    - user_interaction: 0.1 (based on last_accessed_at)
    """
    __tablename__ = "signal_scores"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Composite score
    score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Weighted composite of 5 factors. Invariant D-03."
    )

    # Individual factor scores
    recency_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Factor weight 0.3. Based on updated_at recency."
    )
    link_density_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Factor weight 0.25. Based on edge count."
    )
    completion_state_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Factor weight 0.2. Based on task/goal status."
    )
    reference_frequency_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Factor weight 0.15. Based on incoming edge count."
    )
    user_interaction_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Factor weight 0.1. Based on last_accessed_at recency."
    )

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    version: Mapped[str | None] = mapped_column(Text, default="v1")

    __table_args__ = (
        CheckConstraint("score >= 0.0 AND score <= 1.0", name="signal_score_range"),
        CheckConstraint("recency_score >= 0.0 AND recency_score <= 1.0", name="signal_recency_range"),
        CheckConstraint("link_density_score >= 0.0 AND link_density_score <= 1.0", name="signal_link_density_range"),
        CheckConstraint("completion_state_score >= 0.0 AND completion_state_score <= 1.0", name="signal_completion_range"),
        CheckConstraint("reference_frequency_score >= 0.0 AND reference_frequency_score <= 1.0", name="signal_reference_range"),
        CheckConstraint("user_interaction_score >= 0.0 AND user_interaction_score <= 1.0", name="signal_interaction_range"),
        Index("idx_signal_scores_score", "score"),
        Index("idx_signal_scores_computed", "computed_at"),
    )


class ProgressIntelligence(Base):
    """
    Section 4: Progress intelligence cache table.
    Tracks momentum, consistency streak, and drift score for goals/tasks.

    Invariant D-02: Fully recomputable from task_execution_events + edges.
    Invariant D-03: Non-canonical — stored for display convenience only.

    Refresh schedule:
    - momentum + streak: daily
    - progress: on execution event
    """
    __tablename__ = "progress_intelligence"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Progress ratio (for goals: weighted task completion)
    progress: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Goal/task progress ratio. Invariant D-03."
    )

    # Momentum: weighted tasks completed per week (rolling 4-week avg)
    momentum: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Weighted tasks completed per week (rolling 4-week avg). Invariant D-03."
    )

    # Consistency streak: consecutive days with progress
    consistency_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Consecutive days with progress. Invariant D-03."
    )

    # Drift score: 0=on track, 1=abandoned
    drift_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: 0=on track, 1=abandoned. Based on time since last progress. Invariant D-03."
    )

    # Last progress timestamp
    last_progress_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    version: Mapped[str | None] = mapped_column(Text, default="v1")

    __table_args__ = (
        CheckConstraint("progress >= 0.0 AND progress <= 1.0", name="progress_range"),
        CheckConstraint("momentum >= 0.0", name="momentum_range"),
        CheckConstraint("consistency_streak >= 0", name="streak_range"),
        CheckConstraint("drift_score >= 0.0 AND drift_score <= 1.0", name="drift_range"),
        Index("idx_progress_intelligence_momentum", "momentum"),
        Index("idx_progress_intelligence_drift", "drift_score"),
        Index("idx_progress_intelligence_streak", "consistency_streak"),
    )
