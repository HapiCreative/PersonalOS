"""
Derived layer models (Section 4).
Derived tables store non-canonical, recomputable data for display and ranking.

Invariants:
- D-02: All derived data is fully recomputable from Core + Temporal data.
- D-03: Derived data is non-canonical — never treated as source of truth.
- D-04: Analytics output classification (descriptive/correlational/recommendation).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, Integer, DateTime, Text, ForeignKey, Index, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

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


# =============================================================================
# Phase PC: Analytics rollup tables (Section 4.7 — Derived Layer)
# =============================================================================


class AnalyticsDailyRollup(Base):
    """
    Section 4.7: analytics_daily_rollups derived table.
    Pre-aggregated daily metrics for Tier B analytics (30d+ time ranges).

    Invariant D-02: Fully recomputable from task_execution_events, daily_plans,
                    focus_sessions, journal_nodes, progress_intelligence.
    Invariant D-03: Non-canonical — cached for query performance only.
    Invariant D-04: Analytics output classification enforced at service layer.
    """
    __tablename__ = "analytics_daily_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Task metrics (from task_execution_events)
    tasks_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Count of completed task_execution_events for this date."
    )
    tasks_planned: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Count of tasks in daily_plans.selected_task_ids for this date."
    )
    tasks_planned_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Tasks that were both planned and completed."
    )
    planning_accuracy: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: tasks_planned_completed / tasks_planned (0 if no plan)."
    )

    # Focus metrics (from focus_sessions)
    focus_seconds_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Sum of focus_sessions.duration for this date."
    )
    focus_seconds_by_goal: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="CACHED DERIVED: JSONB mapping goal_id -> focus seconds via goal_tracks_task edges."
    )

    # Journal metrics (from journal_nodes)
    journal_mood_score: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="CACHED DERIVED: Numeric mood score (great=5..bad=1), NULL if no entry."
    )

    # Goal metrics (from progress_intelligence)
    active_goal_progress_delta: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Net change in active goal progress for this date."
    )

    # Streak metric
    streak_eligible_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="CACHED DERIVED: Whether this day counts toward a consistency streak."
    )

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_analytics_daily_user_date"),
        Index("idx_analytics_daily_user", "user_id"),
        Index("idx_analytics_daily_date", "date"),
        Index("idx_analytics_daily_user_date", "user_id", "date"),
    )


class AnalyticsWeeklyRollup(Base):
    """
    Section 4.7: analytics_weekly_rollups derived table.
    Pre-aggregated weekly metrics for Tier B analytics.

    Invariant D-02: Fully recomputable from analytics_daily_rollups + progress_intelligence.
    Invariant D-03: Non-canonical — cached for query performance only.
    Invariant D-04: Analytics output classification enforced at service layer.
    """
    __tablename__ = "analytics_weekly_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_start_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="Monday of the week"
    )

    # Aggregated task metrics
    completion_rate: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: tasks_completed / tasks_planned across the week."
    )
    planning_accuracy: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Average daily planning_accuracy across the week."
    )

    # Focus metrics
    total_focus_time: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="CACHED DERIVED: Sum of focus_seconds_total from daily rollups (seconds)."
    )
    goal_time_distribution: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        comment="CACHED DERIVED: JSONB mapping goal_id -> total focus seconds for the week."
    )

    # Progress metrics
    momentum: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Weighted tasks completed per week (rolling 4-week avg)."
    )
    drift_summary: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="CACHED DERIVED: JSONB array of {goal_id, drift_score} for active goals."
    )

    # Wellbeing metrics
    avg_mood: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="CACHED DERIVED: Average mood score across journal entries for the week."
    )
    mood_productivity_correlation_inputs: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="CACHED DERIVED: Raw inputs for mood-productivity correlation analysis."
    )

    # Metadata
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "week_start_date", name="uq_analytics_weekly_user_week"),
        Index("idx_analytics_weekly_user", "user_id"),
        Index("idx_analytics_weekly_date", "week_start_date"),
        Index("idx_analytics_weekly_user_date", "user_id", "week_start_date"),
    )


# =============================================================================
# Phase PC: Semantic Clustering (Section 4.9 — Derived Layer)
# =============================================================================


class SemanticCluster(Base):
    """
    Section 4.9: semantic_clusters derived table.
    Auto-detected topic clusters using embedding similarity.

    Invariant D-02: Fully recomputable from node embeddings.
    Invariant D-03: Non-canonical — stored for display convenience only.
    """
    __tablename__ = "semantic_clusters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Auto-generated cluster label (derived from member node titles)."
    )
    centroid: Mapped[list | None] = mapped_column(
        Vector(1536), nullable=True,
        comment="CACHED DERIVED: Average embedding of cluster members."
    )
    node_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    coherence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Intra-cluster similarity (0=dispersed, 1=tight)."
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    version: Mapped[str | None] = mapped_column(Text, default="v1")

    __table_args__ = (
        CheckConstraint("coherence_score >= 0.0 AND coherence_score <= 1.0", name="cluster_coherence_range"),
        Index("idx_semantic_clusters_user", "user_id"),
    )


class SemanticClusterMember(Base):
    """
    Section 4.9: semantic_cluster_members derived table.
    Membership table linking nodes to clusters.

    Invariant D-02: Fully recomputable from node embeddings + clustering algorithm.
    Invariant D-03: Non-canonical.
    """
    __tablename__ = "semantic_cluster_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cluster_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("semantic_clusters.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    similarity: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Cosine similarity between node embedding and cluster centroid."
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("cluster_id", "node_id", name="uq_cluster_members"),
        Index("idx_cluster_members_cluster", "cluster_id"),
        Index("idx_cluster_members_node", "node_id"),
    )
