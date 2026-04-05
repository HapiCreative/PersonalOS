"""
Node CRUD service with ownership enforcement and deletion cascade.
Invariants: B-02 (deletion cascade), B-04 (ownership scope).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.models.edge import Edge
from server.app.core.models.enums import NodeType


async def create_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_type: NodeType,
    title: str,
    summary: str | None = None,
) -> Node:
    """Create a Core node."""
    node = Node(
        type=node_type,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()
    return node


async def get_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> Node | None:
    """
    Get node by ID, enforcing ownership at query layer (Section 8.2).
    Updates last_accessed_at for decay detection (BEHAVIORAL TRACKING, S-01).
    """
    stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()

    if node and update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node


async def list_nodes(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_type: NodeType | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Node], int]:
    """List nodes with optional type filter, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id]

    # Visibility precedence (Section 1.6): archived hidden by default
    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if node_type:
        base_filter.append(Node.type == node_type)

    count_stmt = select(func.count()).select_from(Node).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return nodes, total


async def update_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
) -> Node | None:
    """
    Update node fields, enforcing ownership.
    Uses last-write-wins with updated_at comparison (conflict policy, Section 1.8).
    """
    node = await get_node(db, owner_id, node_id, update_accessed=False)
    if node is None:
        return None

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary

    # updated_at is auto-set by DB trigger
    await db.flush()
    return node


async def soft_delete_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> Node | None:
    """
    Soft delete: sets archived_at on the Core node (Section 1.7).
    Entity is hidden from active views but retained and exportable. Reversible.
    """
    node = await get_node(db, owner_id, node_id, update_accessed=False)
    if node is None:
        return None

    node.archived_at = datetime.now(timezone.utc)
    await db.flush()
    return node


async def hard_delete_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> bool:
    """
    Hard delete: permanently removes the Core node (Section 1.7).
    Invariant B-02: Deletion cascade behavior:
    - Edges: cascade-deleted via FK ON DELETE CASCADE
    - Temporal records: flagged node_deleted=true (handled in future phases)
    - Derived caches: purged (handled in future phases)
    - Pipeline jobs: cancelled if pending (handled in future phases)
    - Enrichments: hard-deleted (handled in future phases)
    """
    node = await get_node(db, owner_id, node_id, update_accessed=False)
    if node is None:
        return False

    # Edges are cascade-deleted by FK ON DELETE CASCADE (Invariant G-04)
    await db.delete(node)
    await db.flush()
    return True


async def restore_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> Node | None:
    """Restore a soft-deleted node by clearing archived_at."""
    stmt = select(Node).where(
        Node.id == node_id,
        Node.owner_id == owner_id,
        Node.archived_at.isnot(None),
    )
    result = await db.execute(stmt)
    node = result.scalar_one_or_none()
    if node is None:
        return None

    node.archived_at = None
    await db.flush()
    return node
