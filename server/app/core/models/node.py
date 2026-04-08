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
from sqlalchemy import Computed, Numeric
from server.app.core.models.enums import (
    NodeType, InboxItemStatus, TaskStatus, TaskPriority, Mood,
    SourceType, ProcessingStatus, TriageStatus, Permanence, FragmentType,
    CompileStatus, PipelineStage, MemoryType, GoalStatus, ProjectStatus,
    PipelineJobType, PipelineJobStatus, EnrichmentType, EnrichmentStatus, AIMode,
    AccountType, GoalType, AllocationType,
    FinancialTransactionType, FinancialTransactionStatus,
    CategorySource, TransactionSource, BalanceSnapshotSource, TransactionChangeType,
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

    # Phase 10: ai_summary, ai_takeaways, ai_entities removed.
    # Enrichments now live exclusively in node_enrichments table (Section 4.8).
    # Migration completed in 010_phase10_polish_export_retention.sql.

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


# =============================================================================
# Phase 4: Goal companion table
# =============================================================================


class GoalNode(Base):
    """
    Section 2.4: goal_nodes companion table.
    Goals are strategic objectives that track progress via linked tasks.
    Invariant D-03: progress is non-canonical, stored for display convenience only.

    Finance Module Extension (Section 2.2):
    Adds goal_type discriminator and three nullable financial fields.
    Invariant F-03: financial goals require target_amount + currency non-null;
                    general goals require all three financial fields null.
    """
    __tablename__ = "goal_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[GoalStatus] = mapped_column(nullable=False, default=GoalStatus.ACTIVE)
    start_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    timeframe_label: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Invariant S-01: CACHED DERIVED - weighted sum of completed tasks via goal_tracks_task edges
    # Invariant D-03: Non-canonical, recomputable from task execution events + edges
    progress: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="CACHED DERIVED: Weighted sum of completed tasks via goal_tracks_task edges. Non-canonical (D-03). Invariant S-01."
    )

    milestones: Mapped[dict] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Finance Module Extension (Section 2.2)
    # Invariant F-03: financial → target_amount + currency required; general → all null
    goal_type: Mapped[GoalType] = mapped_column(nullable=False, default=GoalType.GENERAL)
    target_amount = mapped_column(Numeric(15, 2), nullable=True)
    # Invariant S-01: CACHED DERIVED - computed from account allocations via goal_allocations
    current_amount = mapped_column(
        Numeric(15, 2), nullable=True,
        comment="CACHED DERIVED: Computed from account allocations via goal_allocations. Invariant S-01."
    )
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "progress >= 0.0 AND progress <= 1.0",
            name="goal_progress_range",
        ),
        # Invariant F-03: Financial goal field consistency
        CheckConstraint(
            "(goal_type = 'general' AND target_amount IS NULL AND current_amount IS NULL AND currency IS NULL) "
            "OR (goal_type = 'financial' AND target_amount IS NOT NULL AND currency IS NOT NULL)",
            name="goal_financial_field_consistency",
        ),
        Index("idx_goal_nodes_status", "status"),
        Index("idx_goal_nodes_end_date", "end_date", postgresql_where="end_date IS NOT NULL"),
    )


# =============================================================================
# Phase 8: Project companion table
# =============================================================================


class ProjectNode(Base):
    """
    Section 2.4 (TABLE 19): project_nodes companion table.
    Lightweight containers grouping goals and tasks via belongs_to edges.
    Invariant G-05: belongs_to edges restricted to goal→project, task→project.
    """
    __tablename__ = "project_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[ProjectStatus] = mapped_column(nullable=False, default=ProjectStatus.ACTIVE)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)

    __table_args__ = (
        Index("idx_project_nodes_status", "status"),
    )


# =============================================================================
# Phase 9: Pipeline Jobs + Node Enrichments + AI Interaction Logs
# =============================================================================


class PipelineJob(Base):
    """
    Section 7.3: LLM pipeline job tracking.
    Invariant B-04: Pipeline jobs inherit ownership from their target node.
    Retention: 30-day cleanup for completed/failed.
    """
    __tablename__ = "pipeline_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[PipelineJobType] = mapped_column(nullable=False)
    status: Mapped[PipelineJobStatus] = mapped_column(
        nullable=False, default=PipelineJobStatus.PENDING
    )
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_pipeline_jobs_status", "status"),
        Index("idx_pipeline_jobs_type", "job_type"),
        Index("idx_pipeline_jobs_user", "user_id"),
        Index("idx_pipeline_jobs_target", "target_node_id", postgresql_where="target_node_id IS NOT NULL"),
        Index("idx_pipeline_jobs_created", "created_at"),
    )


class NodeEnrichment(Base):
    """
    Section 4.8: Versioned AI enrichments.
    Invariant S-05: One active enrichment per type.
    Only one row per node_id + enrichment_type where superseded_at IS NULL + status=completed.
    Re-enrichment: insert new, supersede old.
    Rollback: supersede current, insert restored copy.
    Retention: 180+ days for superseded enrichments.
    """
    __tablename__ = "node_enrichments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    enrichment_type: Mapped[EnrichmentType] = mapped_column(nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[EnrichmentStatus] = mapped_column(
        nullable=False, default=EnrichmentStatus.PENDING
    )
    prompt_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="NULL = current version. Non-NULL = replaced by newer enrichment. Retention: 180+ days minimum."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    pipeline_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        # Invariant S-05: Only one active (non-superseded, completed) enrichment per node+type
        Index(
            "idx_node_enrichments_active",
            "node_id", "enrichment_type",
            unique=True,
            postgresql_where="superseded_at IS NULL AND status = 'completed'",
        ),
        Index("idx_node_enrichments_node", "node_id"),
        Index("idx_node_enrichments_type", "enrichment_type"),
        Index("idx_node_enrichments_status", "status"),
    )


class AIInteractionLog(Base):
    """
    Section 3.6: Temporal table for AI mode interaction history.
    Invariant T-01: No temporal-to-temporal FKs.
    Invariant T-04: user_id must match owner_id of referenced nodes.
    Invariant T-03: Records retained indefinitely, node_deleted flag on hard-delete.
    """
    __tablename__ = "ai_interaction_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode: Mapped[AIMode] = mapped_column(nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    context_node_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    # Invariant T-03: Temporal retention — never auto-deleted
    node_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_ai_interaction_logs_user", "user_id"),
        Index("idx_ai_interaction_logs_mode", "mode"),
        Index("idx_ai_interaction_logs_created", "created_at"),
    )


# =============================================================================
# Phase F1: Finance Module (Finance Design Rev 3)
# =============================================================================


class AccountNode(Base):
    """
    Section 2.1: account_nodes companion table.
    Accounts are durable, user-owned entities representing bank accounts,
    credit cards, brokerages, wallets, and loans. 1:1 with nodes table.
    The primary bridge between financial behavior (Temporal) and the graph (Core).
    """
    __tablename__ = "account_nodes"

    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    account_type: Mapped[AccountType] = mapped_column(nullable=False)
    institution: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    account_number_masked: Mapped[str | None] = mapped_column(Text, nullable=True)  # last 4 digits only
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_account_nodes_type", "account_type"),
        Index("idx_account_nodes_active", "is_active"),
    )


class GoalAllocation(Base):
    """
    Section 2.6: goal_allocations table.
    Defines what portion of each account's balance contributes toward a financial goal.
    Solves the double-counting problem where multiple goals share the same account.
    Invariant F-06: No shadow graph — relationships are edges + allocations only.
    Invariant F-13: For percentage allocations, SUM of values for a single account
                    across all goals ≤ 1.0 (enforced at application layer).
    """
    __tablename__ = "goal_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    allocation_type: Mapped[AllocationType] = mapped_column(nullable=False)
    value = mapped_column(Numeric(15, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # One allocation per goal-account pair
        Index("uq_goal_allocations_goal_account", "goal_id", "account_id", unique=True),
        # Percentage must be 0.0–1.0; fixed must be non-negative
        CheckConstraint(
            "(allocation_type = 'percentage' AND value >= 0.0 AND value <= 1.0) "
            "OR (allocation_type = 'fixed' AND value >= 0.0)",
            name="goal_allocations_value_check",
        ),
        Index("idx_goal_allocations_goal", "goal_id"),
        Index("idx_goal_allocations_account", "account_id"),
    )


class FinancialCategory(Base):
    """
    Section 2.5: financial_categories table.
    Structured configuration entities with optional hierarchy.
    Invariant F-12: Category deletion blocked by referential integrity
                    (RESTRICT FK on financial_transactions.category_id).
    """
    __tablename__ = "financial_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    icon: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    __table_args__ = (
        # No duplicate category names within the same parent per user
        Index("uq_financial_categories_user_name_parent", "user_id", "name", "parent_id", unique=True),
        Index("idx_financial_categories_user", "user_id"),
        Index("idx_financial_categories_parent", "parent_id", postgresql_where="parent_id IS NOT NULL"),
    )


class FinancialTransaction(Base):
    """
    Section 3.1: financial_transactions table.
    Canonical record of all cash flow events. Temporal layer — never becomes a node.
    Invariant F-01: Transactions never become nodes.
    Invariant F-02: amount always positive, direction in transaction_type.
    Invariant F-08: signed_amount = 0 for pending transactions.
    Invariant F-12: category_id FK with RESTRICT prevents category deletion.
    """
    __tablename__ = "financial_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_type: Mapped[FinancialTransactionType] = mapped_column(nullable=False)
    status: Mapped[FinancialTransactionStatus] = mapped_column(
        nullable=False, default=FinancialTransactionStatus.POSTED
    )

    # Invariant F-02: amount is always positive
    amount = mapped_column(Numeric(15, 2), nullable=False)

    # Invariant F-02 + F-08: signed_amount generated column
    # Positive for inflows, negative for outflows. Pending → 0.
    # Invariant S-01: CACHED DERIVED
    signed_amount = mapped_column(
        Numeric(15, 2),
        Computed(
            "CASE "
            "WHEN status = 'pending' THEN 0 "
            "WHEN transaction_type IN ('income', 'transfer_in', 'refund', 'investment_sell', 'dividend', 'interest') "
            "THEN amount "
            "ELSE -amount "
            "END",
            persisted=True,
        ),
        comment="CACHED DERIVED: Computed from amount * direction sign. Pending → 0. Invariants F-02, F-08, S-01.",
    )

    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217

    # Invariant F-12: RESTRICT prevents category deletion while transactions reference it
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    subcategory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    category_source: Mapped[CategorySource] = mapped_column(
        nullable=False, default=CategorySource.MANUAL
    )

    counterparty: Mapped[str | None] = mapped_column(Text, nullable=True)
    counterparty_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )  # FK deferred to Phase F3 (counterparty_entities)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[TransactionSource] = mapped_column(
        nullable=False, default=TransactionSource.MANUAL
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    is_voided: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        # Invariant F-02: amount must be positive
        CheckConstraint("amount > 0", name="financial_transactions_amount_positive"),
        # Indexes (Section 3.1)
        Index("idx_fin_tx_account_occurred", "account_id", "occurred_at"),
        Index("idx_fin_tx_user_occurred", "user_id", "occurred_at"),
        Index("idx_fin_tx_account_external", "account_id", "external_id", postgresql_where="external_id IS NOT NULL"),
        Index("idx_fin_tx_transfer_group", "transfer_group_id", postgresql_where="transfer_group_id IS NOT NULL"),
        Index("idx_fin_tx_category", "category_id"),
        Index("idx_fin_tx_status", "status"),
        Index("idx_fin_tx_counterparty_entity", "counterparty_entity_id", postgresql_where="counterparty_entity_id IS NOT NULL"),
        # Unique constraint for external_id dedup (idempotent imports)
        Index("uq_fin_tx_account_external_id", "account_id", "external_id", unique=True, postgresql_where="external_id IS NOT NULL"),
    )


class BalanceSnapshot(Base):
    """
    Section 3.2: balance_snapshots table.
    Point-in-time account balance records. Foundation for net worth tracking.
    Invariant F-04: UNIQUE(account_id, snapshot_date) — one per account per date.
    Invariant F-09: Reconciled snapshots are authoritative (enforced at app layer).
    """
    __tablename__ = "balance_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    balance = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    snapshot_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[BalanceSnapshotSource] = mapped_column(
        nullable=False, default=BalanceSnapshotSource.MANUAL
    )
    is_reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        # Invariant F-04: one snapshot per account per date
        Index("uq_balance_snapshots_account_date", "account_id", "snapshot_date", unique=True),
        Index("idx_balance_snapshots_user", "user_id"),
        Index("idx_balance_snapshots_account", "account_id"),
        Index("idx_balance_snapshots_date", "account_id", "snapshot_date"),
    )


class FinancialTransactionHistory(Base):
    """
    Section 3.6: financial_transaction_history table.
    Immutable audit log of all changes to financial_transactions.
    Invariant F-11: Every mutation produces a history row. Append-only, never modified or deleted.
    """
    __tablename__ = "financial_transaction_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_transactions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_type: Mapped[TransactionChangeType] = mapped_column(nullable=False)
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_fin_tx_history_transaction", "transaction_id"),
        Index("idx_fin_tx_history_changed_at", "changed_at"),
    )


class CsvImportMapping(Base):
    """
    Section 5.2: Saved CSV column mappings per account.
    Behavioral layer — stores user's column mapping preferences for repeat imports.
    """
    __tablename__ = "csv_import_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    mapping_name: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    column_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("uq_csv_import_mappings_account_name", "account_id", "mapping_name", unique=True),
        Index("idx_csv_import_mappings_user", "user_id"),
        Index("idx_csv_import_mappings_account", "account_id"),
    )
