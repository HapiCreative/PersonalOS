"""
Journal domain service (Section 2.4, 8.1).
Handles journal entry CRUD with mood and word count tracking.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, JournalNode
from server.app.core.models.enums import NodeType, Mood


def _compute_word_count(text: str) -> int:
    """Compute word count for content. Invariant S-01: CACHED DERIVED."""
    return len(text.split()) if text.strip() else 0


async def create_journal_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    content: str = "",
    entry_date: date | None = None,
    mood: Mood | None = None,
    tags: list[str] | None = None,
) -> tuple[Node, JournalNode]:
    """Create a journal entry (Core node + journal_nodes companion)."""
    node = Node(
        type=NodeType.JOURNAL_ENTRY,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    journal = JournalNode(
        node_id=node.id,
        content=content,
        entry_date=entry_date or date.today(),
        mood=mood,
        tags=tags or [],
        # Invariant S-01: CACHED DERIVED word_count
        word_count=_compute_word_count(content),
    )
    db.add(journal)
    await db.flush()

    return node, journal


async def get_journal_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, JournalNode] | None:
    """Get a journal entry by node ID, enforcing ownership."""
    stmt = (
        select(Node, JournalNode)
        .join(JournalNode, JournalNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, journal = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, journal


async def list_journal_entries(
    db: AsyncSession,
    owner_id: uuid.UUID,
    mood: Mood | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, JournalNode]], int]:
    """List journal entries with optional filters, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.JOURNAL_ENTRY]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if mood:
        base_filter.append(JournalNode.mood == mood)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(JournalNode, JournalNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, JournalNode)
        .join(JournalNode, JournalNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(JournalNode.entry_date.desc(), Node.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_journal_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    mood: Mood | None = ...,  # type: ignore[assignment]
    tags: list[str] | None = ...,  # type: ignore[assignment]
) -> tuple[Node, JournalNode] | None:
    """Update journal entry fields, enforcing ownership."""
    pair = await get_journal_entry(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, journal = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if content is not None:
        journal.content = content
        # Invariant S-01: CACHED DERIVED word_count
        journal.word_count = _compute_word_count(content)
    if mood is not ...:
        journal.mood = mood
    if tags is not ...:
        journal.tags = tags or []

    await db.flush()
    return node, journal
