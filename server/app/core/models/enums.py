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


class EdgeRelationType(str, enum.Enum):
    """Section 2.3: Edge relation taxonomy (all 11 types)."""
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
