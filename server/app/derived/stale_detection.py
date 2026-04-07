"""
Stale content detection service (Section 4.6).
Derived layer: computes stale flags from Core data.

Per-entity staleness thresholds (Table 31):
- task (todo): 14 days untouched
- task (in_progress): 7 days untouched
- goal (active): 30 days no progress
- kb_entry (accepted): 90 days since lint
- inbox_item (pending): 3 days unclassified
- source_item (raw): 7 days unprocessed

Invariant D-01: All stale flags use DerivedExplanation.
Invariant D-02: Recomputability — fully recomputable from Core + Temporal data.
Invariant D-03: Non-canonical storage — never stored on canonical nodes.

Visibility precedence (Section 1.6): archived > snoozed > stale.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import (
    Node, TaskNode, GoalNode, KBNode, InboxItem, SourceItemNode,
)
from server.app.core.models.enums import (
    NodeType, TaskStatus, GoalStatus, CompileStatus,
    InboxItemStatus, ProcessingStatus,
)
from server.app.derived.schemas import DerivedExplanation, DerivedFactor


# =============================================================================
# Staleness thresholds (Section 4.6, Table 31)
# =============================================================================
STALE_THRESHOLDS = {
    "task_todo": timedelta(days=14),
    "task_in_progress": timedelta(days=7),
    "goal_active": timedelta(days=30),
    "kb_accepted": timedelta(days=90),
    "inbox_pending": timedelta(days=3),
    "source_raw": timedelta(days=7),
}

STALE_PROMPTS = {
    "task_todo": "Still relevant?",
    "task_in_progress": "Blocked or deprioritized?",
    "goal_active": "Pause or adjust?",
    "kb_accepted": "Still accurate?",
    "inbox_pending": "Unprocessed items waiting",
    "source_raw": "Worth normalizing?",
}


@dataclass
class StaleItem:
    """A single stale item in the cleanup queue."""
    node_id: uuid.UUID
    node_type: str
    title: str
    stale_category: str  # e.g. "task_todo", "goal_active"
    days_stale: int
    last_activity_at: datetime | None
    prompt: str
    # Invariant D-01: Every stale flag uses DerivedExplanation
    explanation: DerivedExplanation
    snoozed_until: datetime | None = None
    metadata: dict = field(default_factory=dict)


def _build_stale_explanation(
    category: str,
    days_stale: int,
    threshold_days: int,
    last_activity: datetime | None,
) -> DerivedExplanation:
    """
    Invariant D-01: Build a DerivedExplanation for a stale flag.
    Every stale detection result must include summary + factors.
    """
    prompt = STALE_PROMPTS.get(category, "Needs attention")

    factors = [
        DerivedFactor(
            signal="days_untouched",
            value=days_stale,
            weight=0.6,
        ),
        DerivedFactor(
            signal="threshold_days",
            value=threshold_days,
            weight=0.3,
        ),
    ]
    if last_activity:
        factors.append(DerivedFactor(
            signal="last_activity",
            value=last_activity.isoformat(),
            weight=0.1,
        ))

    explanation = DerivedExplanation(
        summary=f"{prompt} — untouched for {days_stale} days (threshold: {threshold_days} days)",
        factors=factors,
        confidence=min(1.0, days_stale / (threshold_days * 2)),  # Confidence grows with staleness
        generated_at=datetime.now(timezone.utc),
        version="v1",
    )
    # Invariant D-01: Validate before returning
    DerivedExplanation.validate(explanation)
    return explanation


async def detect_stale_tasks(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect stale tasks (Section 4.6, Table 31).
    - task (todo): 14 days untouched
    - task (in_progress): 7 days untouched
    """
    if now is None:
        now = datetime.now(timezone.utc)

    items = []

    # Stale todo tasks: 14 days untouched
    todo_threshold = now - STALE_THRESHOLDS["task_todo"]
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status == TaskStatus.TODO,
            Node.updated_at < todo_threshold,
        )
        .order_by(Node.updated_at.asc())
    )
    result = await db.execute(stmt)
    for node, task in result.all():
        days = (now - node.updated_at.replace(tzinfo=timezone.utc if node.updated_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="task",
            title=node.title,
            stale_category="task_todo",
            days_stale=days,
            last_activity_at=node.updated_at,
            prompt=STALE_PROMPTS["task_todo"],
            explanation=_build_stale_explanation("task_todo", days, 14, node.updated_at),
            metadata={"status": task.status.value, "priority": task.priority.value},
        ))

    # Stale in_progress tasks: 7 days untouched
    ip_threshold = now - STALE_THRESHOLDS["task_in_progress"]
    stmt = (
        select(Node, TaskNode)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
            TaskNode.status == TaskStatus.IN_PROGRESS,
            Node.updated_at < ip_threshold,
        )
        .order_by(Node.updated_at.asc())
    )
    result = await db.execute(stmt)
    for node, task in result.all():
        days = (now - node.updated_at.replace(tzinfo=timezone.utc if node.updated_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="task",
            title=node.title,
            stale_category="task_in_progress",
            days_stale=days,
            last_activity_at=node.updated_at,
            prompt=STALE_PROMPTS["task_in_progress"],
            explanation=_build_stale_explanation("task_in_progress", days, 7, node.updated_at),
            metadata={"status": task.status.value, "priority": task.priority.value},
        ))

    return items


async def detect_stale_goals(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect stale goals (Section 4.6, Table 31).
    - goal (active): 30 days no progress
    """
    if now is None:
        now = datetime.now(timezone.utc)

    threshold = now - STALE_THRESHOLDS["goal_active"]

    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
            Node.archived_at.is_(None),
            GoalNode.status == GoalStatus.ACTIVE,
            Node.updated_at < threshold,
        )
        .order_by(Node.updated_at.asc())
    )
    result = await db.execute(stmt)
    items = []
    for node, goal in result.all():
        days = (now - node.updated_at.replace(tzinfo=timezone.utc if node.updated_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="goal",
            title=node.title,
            stale_category="goal_active",
            days_stale=days,
            last_activity_at=node.updated_at,
            prompt=STALE_PROMPTS["goal_active"],
            explanation=_build_stale_explanation("goal_active", days, 30, node.updated_at),
            metadata={
                "status": goal.status.value,
                "progress": goal.progress,
            },
        ))
    return items


async def detect_stale_kb(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect stale KB entries (Section 4.6, Table 31).
    - kb_entry (accepted): 90 days since lint
    """
    if now is None:
        now = datetime.now(timezone.utc)

    threshold = now - STALE_THRESHOLDS["kb_accepted"]

    stmt = (
        select(Node, KBNode)
        .join(KBNode, KBNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.KB_ENTRY,
            Node.archived_at.is_(None),
            KBNode.compile_status == CompileStatus.ACCEPT,
            Node.updated_at < threshold,
        )
        .order_by(Node.updated_at.asc())
    )
    result = await db.execute(stmt)
    items = []
    for node, kb in result.all():
        days = (now - node.updated_at.replace(tzinfo=timezone.utc if node.updated_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="kb_entry",
            title=node.title,
            stale_category="kb_accepted",
            days_stale=days,
            last_activity_at=node.updated_at,
            prompt=STALE_PROMPTS["kb_accepted"],
            explanation=_build_stale_explanation("kb_accepted", days, 90, node.updated_at),
            metadata={
                "compile_status": kb.compile_status.value,
                "compile_version": kb.compile_version,
            },
        ))
    return items


async def detect_stale_inbox(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect stale inbox items (Section 4.6, Table 31).
    - inbox_item (pending): 3 days unclassified
    """
    if now is None:
        now = datetime.now(timezone.utc)

    threshold = now - STALE_THRESHOLDS["inbox_pending"]

    stmt = (
        select(Node, InboxItem)
        .join(InboxItem, InboxItem.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.INBOX_ITEM,
            Node.archived_at.is_(None),
            InboxItem.status == InboxItemStatus.PENDING,
            Node.created_at < threshold,
        )
        .order_by(Node.created_at.asc())
    )
    result = await db.execute(stmt)
    items = []
    for node, inbox in result.all():
        days = (now - node.created_at.replace(tzinfo=timezone.utc if node.created_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="inbox_item",
            title=node.title,
            stale_category="inbox_pending",
            days_stale=days,
            last_activity_at=node.created_at,
            prompt=STALE_PROMPTS["inbox_pending"],
            explanation=_build_stale_explanation("inbox_pending", days, 3, node.created_at),
            metadata={"status": inbox.status.value},
        ))
    return items


async def detect_stale_sources(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect stale source items (Section 4.6, Table 31).
    - source_item (raw): 7 days unprocessed
    """
    if now is None:
        now = datetime.now(timezone.utc)

    threshold = now - STALE_THRESHOLDS["source_raw"]

    stmt = (
        select(Node, SourceItemNode)
        .join(SourceItemNode, SourceItemNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.SOURCE_ITEM,
            Node.archived_at.is_(None),
            SourceItemNode.processing_status == ProcessingStatus.RAW,
            Node.created_at < threshold,
        )
        .order_by(Node.created_at.asc())
    )
    result = await db.execute(stmt)
    items = []
    for node, source in result.all():
        days = (now - node.created_at.replace(tzinfo=timezone.utc if node.created_at.tzinfo is None else None)).days
        items.append(StaleItem(
            node_id=node.id,
            node_type="source_item",
            title=node.title,
            stale_category="source_raw",
            days_stale=days,
            last_activity_at=node.created_at,
            prompt=STALE_PROMPTS["source_raw"],
            explanation=_build_stale_explanation("source_raw", days, 7, node.created_at),
            metadata={
                "source_type": source.source_type.value,
                "processing_status": source.processing_status.value,
            },
        ))
    return items


async def detect_all_stale(
    db: AsyncSession,
    owner_id: uuid.UUID,
    now: datetime | None = None,
) -> list[StaleItem]:
    """
    Detect all stale items across all entity types.
    Returns a combined list sorted by days_stale descending.

    Invariant D-01: All items include DerivedExplanation.
    Invariant D-02: All results are recomputable from Core data.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    all_items: list[StaleItem] = []
    all_items.extend(await detect_stale_tasks(db, owner_id, now))
    all_items.extend(await detect_stale_goals(db, owner_id, now))
    all_items.extend(await detect_stale_kb(db, owner_id, now))
    all_items.extend(await detect_stale_inbox(db, owner_id, now))
    all_items.extend(await detect_stale_sources(db, owner_id, now))

    # Sort by staleness (most stale first)
    all_items.sort(key=lambda x: x.days_stale, reverse=True)
    return all_items


async def check_node_stale(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> StaleItem | None:
    """Check if a specific node is stale. Returns StaleItem or None."""
    now = datetime.now(timezone.utc)

    # Get the node
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    )
    node = result.scalar_one_or_none()
    if node is None or node.archived_at is not None:
        return None

    if node.type == NodeType.TASK:
        items = await detect_stale_tasks(db, owner_id, now)
    elif node.type == NodeType.GOAL:
        items = await detect_stale_goals(db, owner_id, now)
    elif node.type == NodeType.KB_ENTRY:
        items = await detect_stale_kb(db, owner_id, now)
    elif node.type == NodeType.INBOX_ITEM:
        items = await detect_stale_inbox(db, owner_id, now)
    elif node.type == NodeType.SOURCE_ITEM:
        items = await detect_stale_sources(db, owner_id, now)
    else:
        return None

    for item in items:
        if item.node_id == node_id:
            return item
    return None
