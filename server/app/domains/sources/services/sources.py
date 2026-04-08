"""
Source item CRUD and deduplication services (Section 6, 8.1).

Invariants enforced:
- B-04: Ownership scope
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    NodeType, Permanence, ProcessingStatus, SourceType, TriageStatus,
)
from server.app.core.models.node import Node, SourceItemNode
from server.app.core.services.embedding import compute_checksum, generate_embedding


async def create_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    source_type: SourceType = SourceType.OTHER,
    url: str | None = None,
    author: str | None = None,
    platform: str | None = None,
    published_at: datetime | None = None,
    capture_context: str | None = None,
    raw_content: str = "",
    permanence: Permanence = Permanence.REFERENCE,
) -> tuple[Node, SourceItemNode]:
    """
    Create a source item (Core node + source_item_nodes companion).
    Stage 1 of the 4-stage capture workflow: capture.
    Includes deduplication checks.
    """
    # Deduplication: exact URL match
    if url:
        existing_stmt = (
            select(SourceItemNode)
            .join(Node, Node.id == SourceItemNode.node_id)
            .where(
                Node.owner_id == owner_id,
                SourceItemNode.url == url,
                Node.archived_at.is_(None),
            )
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"Duplicate source: URL already captured (node_id={existing.node_id})")

    # Compute checksum for content deduplication
    checksum = compute_checksum(raw_content) if raw_content else None

    # Deduplication: exact content checksum match
    if checksum:
        existing_stmt = (
            select(SourceItemNode)
            .join(Node, Node.id == SourceItemNode.node_id)
            .where(
                Node.owner_id == owner_id,
                SourceItemNode.checksum == checksum,
                Node.archived_at.is_(None),
            )
        )
        existing = (await db.execute(existing_stmt)).scalar_one_or_none()
        if existing is not None:
            raise ValueError(f"Duplicate source: Content checksum match (node_id={existing.node_id})")

    # Create Core node
    node = Node(
        type=NodeType.SOURCE_ITEM,
        owner_id=owner_id,
        title=title,
        summary=summary or (raw_content[:200] if raw_content else None),
    )
    db.add(node)
    await db.flush()

    # Create companion table record
    source = SourceItemNode(
        node_id=node.id,
        source_type=source_type,
        url=url,
        author=author,
        platform=platform,
        published_at=published_at,
        capture_context=capture_context,
        raw_content=raw_content,
        processing_status=ProcessingStatus.RAW,
        triage_status=TriageStatus.UNREVIEWED,
        permanence=permanence,
        checksum=checksum,
    )
    db.add(source)
    await db.flush()

    # Generate embedding for the node (async, non-blocking if provider unavailable)
    embedding = await generate_embedding(f"{title} {raw_content[:500]}")
    if embedding:
        node.embedding = embedding
        await db.flush()

    return node, source


async def get_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, SourceItemNode] | None:
    """Get a source item by node ID, enforcing ownership."""
    stmt = (
        select(Node, SourceItemNode)
        .join(SourceItemNode, SourceItemNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, source = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, source


async def list_sources(
    db: AsyncSession,
    owner_id: uuid.UUID,
    processing_status: ProcessingStatus | None = None,
    triage_status: TriageStatus | None = None,
    source_type: SourceType | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, SourceItemNode]], int]:
    """
    List source items with optional filters.
    Supports the 6 source inbox views: All, Raw, Ready, Promoted, Dismissed, Archived.
    """
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.SOURCE_ITEM]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if processing_status:
        base_filter.append(SourceItemNode.processing_status == processing_status)
    if triage_status:
        base_filter.append(SourceItemNode.triage_status == triage_status)
    if source_type:
        base_filter.append(SourceItemNode.source_type == source_type)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(SourceItemNode, SourceItemNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, SourceItemNode)
        .join(SourceItemNode, SourceItemNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(SourceItemNode.captured_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    source_type: SourceType | None = None,
    url: str | None = None,
    author: str | None = None,
    platform: str | None = None,
    capture_context: str | None = None,
    raw_content: str | None = None,
    canonical_content: str | None = None,
    permanence: Permanence | None = None,
    processing_status: ProcessingStatus | None = None,
    triage_status: TriageStatus | None = None,
) -> tuple[Node, SourceItemNode] | None:
    """Update source item fields, enforcing ownership."""
    pair = await get_source(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, source = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if source_type is not None:
        source.source_type = source_type
    if url is not None:
        source.url = url
    if author is not None:
        source.author = author
    if platform is not None:
        source.platform = platform
    if capture_context is not None:
        source.capture_context = capture_context
    if raw_content is not None:
        source.raw_content = raw_content
        source.checksum = compute_checksum(raw_content)
    if canonical_content is not None:
        source.canonical_content = canonical_content
    if permanence is not None:
        source.permanence = permanence
    if processing_status is not None:
        source.processing_status = processing_status
    if triage_status is not None:
        source.triage_status = triage_status

    await db.flush()
    return node, source


async def check_duplicate_by_embedding(
    db: AsyncSession,
    owner_id: uuid.UUID,
    embedding: list[float],
    threshold: float = 0.95,
) -> uuid.UUID | None:
    """
    Source deduplication via embedding similarity > threshold.
    Returns the node_id of the duplicate if found, None otherwise.
    """
    from pgvector.sqlalchemy import Vector

    stmt = (
        select(
            Node.id,
            Node.embedding.cosine_distance(embedding).label("distance"),
        )
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.SOURCE_ITEM,
            Node.archived_at.is_(None),
            Node.embedding.isnot(None),
        )
        .order_by("distance")
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()

    if row is not None:
        node_id, distance = row
        similarity = 1.0 - distance
        if similarity >= threshold:
            return node_id

    return None
