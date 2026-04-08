"""
Inbox domain service.
Handles inbox item creation, status transitions, and queries.
Ownership enforcement at query layer (Section 8.2).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import InboxItemStatus, NodeType
from server.app.core.models.node import InboxItem, Node


async def create_inbox_item(
    db: AsyncSession,
    owner_id: uuid.UUID,
    raw_text: str,
    title: str | None = None,
) -> tuple[Node, InboxItem]:
    """Create a new inbox item (Core node + companion table)."""
    # Auto-generate title from first 80 chars of raw_text if not provided
    if not title:
        title = raw_text[:80].strip()
        if len(raw_text) > 80:
            title += "..."

    node = Node(
        type=NodeType.INBOX_ITEM,
        owner_id=owner_id,
        title=title,
        summary=raw_text[:200] if len(raw_text) > 200 else raw_text,
    )
    db.add(node)
    await db.flush()

    inbox_item = InboxItem(
        node_id=node.id,
        raw_text=raw_text,
        status=InboxItemStatus.PENDING,
    )
    db.add(inbox_item)
    await db.flush()

    return node, inbox_item


async def get_inbox_item(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, InboxItem] | None:
    """Get inbox item by node_id, enforcing ownership (Section 8.2)."""
    stmt = (
        select(Node, InboxItem)
        .join(InboxItem, InboxItem.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None
    return row.tuple()


async def list_inbox_items(
    db: AsyncSession,
    owner_id: uuid.UUID,
    status: InboxItemStatus | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, InboxItem]], int]:
    """List inbox items with optional status filter, enforcing ownership."""
    base_filter = [
        Node.owner_id == owner_id,
        Node.type == NodeType.INBOX_ITEM,
    ]
    # Visibility precedence (Section 1.6): archived hidden by default
    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if status:
        base_filter.append(InboxItem.status == status)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(InboxItem, InboxItem.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, InboxItem)
        .join(InboxItem, InboxItem.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = [row.tuple() for row in result.all()]

    return items, total


async def update_inbox_item(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    raw_text: str | None = None,
    status: InboxItemStatus | None = None,
    title: str | None = None,
) -> tuple[Node, InboxItem] | None:
    """Update inbox item fields, enforcing ownership."""
    pair = await get_inbox_item(db, owner_id, node_id)
    if pair is None:
        return None

    node, inbox_item = pair

    if title is not None:
        node.title = title
    if raw_text is not None:
        inbox_item.raw_text = raw_text
        node.summary = raw_text[:200] if len(raw_text) > 200 else raw_text
    if status is not None:
        inbox_item.status = status

    await db.flush()
    return node, inbox_item
