"""
Enums matching the database schema exactly (Section 2).
All enum values must match the architecture doc.
"""

import enum


class NodeType(str, enum.Enum):
    """Section 2.2: Node types for the graph identity layer."""
    KB_ENTRY = "kb_entry"
    TASK = "task"
    JOURNAL_ENTRY = "journal_entry"
    GOAL = "goal"
    MEMORY = "memory"
    SOURCE_ITEM = "source_item"
    INBOX_ITEM = "inbox_item"
    PROJECT = "project"
    ACCOUNT = "account"  # Finance Module (Section 2.1)
    OBLIGATION = "obligation"  # Finance Phase F2 (Obligations Addendum Section 2)


class EdgeRelationType(str, enum.Enum):
    """Section 2.3: Edge relation taxonomy (all 11 types + finance)."""
    SEMANTIC_REFERENCE = "semantic_reference"
    DERIVED_FROM_SOURCE = "derived_from_source"
    PARENT_CHILD = "parent_child"
    BELONGS_TO = "belongs_to"
    GOAL_TRACKS_TASK = "goal_tracks_task"
    GOAL_TRACKS_KB = "goal_tracks_kb"
    BLOCKED_BY = "blocked_by"
    JOURNAL_REFLECTS_ON = "journal_reflects_on"
    SOURCE_SUPPORTS_GOAL = "source_supports_goal"
    SOURCE_QUOTED_IN = "source_quoted_in"
    CAPTURED_FOR = "captured_for"
    ACCOUNT_FUNDS_GOAL = "account_funds_goal"  # Finance Module (Section 2.3)
    OBLIGATION_CHARGES_ACCOUNT = "obligation_charges_account"  # F2.6: obligation → account
    OBLIGATION_IMPACTS_GOAL = "obligation_impacts_goal"  # F2.6: obligation → goal


class EdgeOrigin(str, enum.Enum):
    """Section 2.3: Who created the edge."""
    USER = "user"
    SYSTEM = "system"
    LLM = "llm"


class EdgeState(str, enum.Enum):
    """Section 2.3: Edge lifecycle state."""
    ACTIVE = "active"
    PENDING_REVIEW = "pending_review"
    DISMISSED = "dismissed"


class InboxItemStatus(str, enum.Enum):
    """Section 2.4: Inbox item lifecycle."""
    PENDING = "pending"
    PROMOTED = "promoted"
    DISMISSED = "dismissed"
    MERGED = "merged"
    ARCHIVED = "archived"


class TaskStatus(str, enum.Enum):
    """Section 2.4: Task status lifecycle.
    Invariant B-03: Formal transition validation.
    Invariant S-02: recurring + done = invalid.
    """
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, enum.Enum):
    """Section 2.4: Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Mood(str, enum.Enum):
    """Section 2.4: Journal mood ENUM (v6 change from free TEXT)."""
    GREAT = "great"
    GOOD = "good"
    NEUTRAL = "neutral"
    LOW = "low"
    BAD = "bad"


class TaskExecutionEventType(str, enum.Enum):
    """Section 3.7: Execution event types."""
    COMPLETED = "completed"
    SKIPPED = "skipped"
    DEFERRED = "deferred"


class TemplateTargetType(str, enum.Enum):
    """Section 2.4: Template target types."""
    GOAL = "goal"
    TASK = "task"
    JOURNAL_ENTRY = "journal_entry"


# =============================================================================
# Phase 3: Sources + KB + Memory enums
# =============================================================================


class SourceType(str, enum.Enum):
    """Section 6: Source item types."""
    ARTICLE = "article"
    TWEET = "tweet"
    BOOKMARK = "bookmark"
    NOTE = "note"
    PODCAST = "podcast"
    VIDEO = "video"
    PDF = "pdf"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    """Section 6: Source processing pipeline status (4-stage)."""
    RAW = "raw"
    NORMALIZED = "normalized"
    ENRICHED = "enriched"
    ERROR = "error"


class TriageStatus(str, enum.Enum):
    """Section 6: Human triage decision on source items."""
    UNREVIEWED = "unreviewed"
    READY = "ready"
    PROMOTED = "promoted"
    DISMISSED = "dismissed"


class Permanence(str, enum.Enum):
    """Section 6: Source item permanence classification."""
    EPHEMERAL = "ephemeral"
    REFERENCE = "reference"
    CANONICAL = "canonical"


class FragmentType(str, enum.Enum):
    """Section 6: Source fragment types."""
    PARAGRAPH = "paragraph"
    QUOTE = "quote"
    HEADING = "heading"
    LIST_ITEM = "list_item"
    CODE = "code"
    IMAGE_REF = "image_ref"


class CompileStatus(str, enum.Enum):
    """Section 7: KB compilation pipeline (6-stage).
    ingest -> parse -> compile -> review -> accept -> stale
    """
    INGEST = "ingest"
    PARSE = "parse"
    COMPILE = "compile"
    REVIEW = "review"
    ACCEPT = "accept"
    STALE = "stale"


class PipelineStage(str, enum.Enum):
    """Section 7: KB lifecycle pipeline stage (5-stage)."""
    DRAFT = "draft"
    REVIEW = "review"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MemoryType(str, enum.Enum):
    """Section 2.4: Memory node types."""
    DECISION = "decision"
    INSIGHT = "insight"
    LESSON = "lesson"
    PRINCIPLE = "principle"
    PREFERENCE = "preference"


# =============================================================================
# Phase 4: Goals enums
# =============================================================================


class GoalStatus(str, enum.Enum):
    """Section 2.4: Goal lifecycle status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# =============================================================================
# Phase 8: Projects enums
# =============================================================================


class ProjectStatus(str, enum.Enum):
    """Section 2.4: Project lifecycle status."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# =============================================================================
# Phase 9: AI Pipeline + Enrichments enums
# =============================================================================


class PipelineJobType(str, enum.Enum):
    """Section 7.3: Pipeline job types for LLM operations."""
    COMPILE = "compile"
    LINT = "lint"
    EMBED = "embed"
    SUGGEST_LINKS = "suggest_links"
    NORMALIZE_SOURCE = "normalize_source"
    ENRICH_SOURCE = "enrich_source"
    CLASSIFY_INBOX = "classify_inbox"


class PipelineJobStatus(str, enum.Enum):
    """Section 7.3: Pipeline job lifecycle status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EnrichmentType(str, enum.Enum):
    """Section 4.8: Node enrichment types."""
    SUMMARY = "summary"
    TAKEAWAYS = "takeaways"
    ENTITIES = "entities"


class EnrichmentStatus(str, enum.Enum):
    """Section 4.8: Enrichment processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AIMode(str, enum.Enum):
    """Section 5.5: AI interaction modes."""
    ASK = "ask"
    PLAN = "plan"
    REFLECT = "reflect"
    IMPROVE = "improve"


# =============================================================================
# Finance Module enums (Finance Design Rev 3)
# =============================================================================


class AccountType(str, enum.Enum):
    """Section 2.1: Account types for financial accounts."""
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    BROKERAGE = "brokerage"
    CRYPTO_WALLET = "crypto_wallet"
    CASH = "cash"
    LOAN = "loan"
    MORTGAGE = "mortgage"
    OTHER = "other"


class GoalType(str, enum.Enum):
    """Section 2.2: Goal type discriminator for financial vs general goals."""
    GENERAL = "general"
    FINANCIAL = "financial"


class AllocationType(str, enum.Enum):
    """Section 2.6: Goal allocation type."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"


class FinancialTransactionType(str, enum.Enum):
    """Section 3.1: All 11 transaction types."""
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    INVESTMENT_BUY = "investment_buy"
    INVESTMENT_SELL = "investment_sell"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class FinancialTransactionStatus(str, enum.Enum):
    """Section 3.1: Transaction status lifecycle."""
    PENDING = "pending"
    POSTED = "posted"
    SETTLED = "settled"


class CategorySource(str, enum.Enum):
    """Section 3.1: How category was assigned to a transaction."""
    MANUAL = "manual"
    SYSTEM_SUGGESTED = "system_suggested"
    IMPORTED = "imported"


class TransactionSource(str, enum.Enum):
    """Section 3.1: Data origin of a transaction."""
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"
    API_SYNC = "api_sync"


class BalanceSnapshotSource(str, enum.Enum):
    """Section 3.2: Data origin of a balance snapshot."""
    MANUAL = "manual"
    CSV_IMPORT = "csv_import"
    API_SYNC = "api_sync"
    COMPUTED = "computed"


class TransactionChangeType(str, enum.Enum):
    """Section 3.6: Transaction history change types."""
    CREATE = "create"
    UPDATE = "update"
    VOID = "void"


# =============================================================================
# Finance Phase F2 enums (Finance Design Rev 3 + Obligations Addendum)
# =============================================================================


class InvestmentAssetType(str, enum.Enum):
    """Section 3.3: Asset types for investment holdings."""
    STOCK = "stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    CRYPTO = "crypto"
    OPTION = "option"
    OTHER = "other"


class InvestmentTransactionType(str, enum.Enum):
    """Section 3.4: Investment transaction types."""
    BUY = "buy"
    SELL = "sell"
    DIVIDEND_REINVEST = "dividend_reinvest"
    SPLIT = "split"
    MERGER = "merger"
    SPINOFF = "spinoff"


class ValuationSource(str, enum.Enum):
    """Section 3.3: How a holding's valuation was determined."""
    MARKET_API = "market_api"
    MANUAL = "manual"
    COMPUTED = "computed"


class ObligationType(str, enum.Enum):
    """Obligations Addendum Section 2: Obligation category types."""
    SUBSCRIPTION = "subscription"
    UTILITY = "utility"
    RENT = "rent"
    LOAN = "loan"
    INSURANCE = "insurance"
    TAX = "tax"
    MEMBERSHIP = "membership"
    OTHER = "other"


class AmountModel(str, enum.Enum):
    """Obligations Addendum Section 2: How the obligation amount behaves."""
    FIXED = "fixed"
    VARIABLE = "variable"
    SEASONAL = "seasonal"


class ObligationStatus(str, enum.Enum):
    """Obligations Addendum Section 2: Obligation lifecycle status."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ObligationOrigin(str, enum.Enum):
    """Obligations Addendum Section 2: How the obligation was created."""
    MANUAL = "manual"
    DETECTED = "detected"


class BreakdownComponentType(str, enum.Enum):
    """Obligations Addendum Section 2: Breakdown component types."""
    BASE = "base"
    USAGE = "usage"
    TAX = "tax"
    FEE = "fee"
    DISCOUNT = "discount"
    ADJUSTMENT = "adjustment"
    OTHER = "other"


class BreakdownAmountModel(str, enum.Enum):
    """Obligations Addendum Section 2: Breakdown amount model (extends AmountModel with percentage)."""
    FIXED = "fixed"
    VARIABLE = "variable"
    SEASONAL = "seasonal"
    PERCENTAGE = "percentage"


class BreakdownStatus(str, enum.Enum):
    """Obligations Addendum Section 2: Breakdown version status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class AlertType(str, enum.Enum):
    """Section 5.1 + Obligations Addendum Section 5: Finance alert taxonomy."""
    # Rule-based (F2.4)
    LOW_CASH_RUNWAY = "low_cash_runway"
    LARGE_TRANSACTION = "large_transaction"
    UNCATEGORIZED_AGING = "uncategorized_aging"
    DUPLICATE_IMPORT = "duplicate_import"
    STALE_PENDING = "stale_pending"
    GOAL_OFF_TRACK = "goal_off_track"
    UNRECONCILED_DIVERGENCE = "unreconciled_divergence"
    BROKEN_TRANSFER = "broken_transfer"
    # Rule-based obligation alerts (F2.6)
    UPCOMING_OBLIGATION = "upcoming_obligation"
    MISSED_OBLIGATION = "missed_obligation"
    OBLIGATION_AMOUNT_SPIKE = "obligation_amount_spike"
    OBLIGATION_RATE_CHANGE = "obligation_rate_change"
    OBLIGATION_EXPIRING = "obligation_expiring"


class AlertSeverity(str, enum.Enum):
    """Section 5.1: Finance alert severity levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(str, enum.Enum):
    """Section 5.1: Finance alert lifecycle status."""
    ACTIVE = "active"
    DISMISSED = "dismissed"
    SNOOZED = "snoozed"
    RESOLVED = "resolved"


class PortfolioRollupPeriodType(str, enum.Enum):
    """Section 4.8: Portfolio rollup period granularity."""
    DAILY = "daily"
    MONTHLY = "monthly"
