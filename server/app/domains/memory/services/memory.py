"""
Memory domain service (Section 2.4, 8.1).
Handles memory node CRUD for decisions, insights, lessons, principles, preferences.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import MemoryType, NodeType
from server.app.core.models.node import MemoryNode, Node
from server.app.core.services.embedding import generate_embedding


async def create_memory(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    memory_type: MemoryType,
    summary: str | None = None,
    content: str = "",
    context: str | None = None,
    review_at: datetime | None = None,
    tags: list[str] | None = None,
) -> tuple[Node, MemoryNode]:
    """Create a memory node (Core node + memory_nodes companion)."""
    node = Node(
        type=NodeType.MEMORY,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    memory = MemoryNode(
        node_id=node.id,
        memory_type=memory_type,
        content=content,
        context=context,
        review_at=review_at,
        tags=tags or [],
    )
    db.add(memory)
    await db.flush()

    # Generate embedding
    embed_text = f"{title} {content[:500]}"
    embedding = await generate_embedding(embed_text)
    if embedding:
        node.embedding = embedding
        await db.flush()

    return node, memory


async def get_memory(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, MemoryNode] | None:
    """Get a memory node by node ID, enforcing ownership."""
    stmt = (
        select(Node, MemoryNode)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, memory = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, memory


async def list_memories(
    db: AsyncSession,
    owner_id: uuid.UUID,
    memory_type: MemoryType | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, MemoryNode]], int]:
    """List memory nodes with optional type filter, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.MEMORY]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if memory_type:
        base_filter.append(MemoryNode.memory_type == memory_type)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, MemoryNode)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_memory(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    context: str | None = None,
    review_at: datetime | None = ...,  # type: ignore[assignment]
    tags: list[str] | None = None,
) -> tuple[Node, MemoryNode] | None:
    """Update memory node fields, enforcing ownership."""
    pair = await get_memory(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, memory = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if content is not None:
        memory.content = content
    if context is not None:
        memory.context = context
    if review_at is not ...:
        memory.review_at = review_at
    if tags is not None:
        memory.tags = tags

    await db.flush()

    # Re-generate embedding if content changed
    if content is not None or title is not None:
        embed_text = f"{node.title} {memory.content[:500]}"
        embedding = await generate_embedding(embed_text)
        if embedding:
            node.embedding = embedding
            await db.flush()

    return node, memory
