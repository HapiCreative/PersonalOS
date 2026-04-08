"""Source fragment services."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import FragmentType, NodeType
from server.app.core.models.node import Node, SourceFragment
from server.app.core.services.embedding import generate_embedding


async def create_fragment(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source_node_id: uuid.UUID,
    fragment_text: str,
    position: int = 0,
    fragment_type: FragmentType = FragmentType.PARAGRAPH,
    section_ref: str | None = None,
) -> SourceFragment:
    """Create a source fragment. Verifies source ownership."""
    # Verify source exists and is owned by user
    source_node = await db.execute(
        select(Node).where(
            Node.id == source_node_id,
            Node.owner_id == owner_id,
            Node.type == NodeType.SOURCE_ITEM,
        )
    )
    if source_node.scalar_one_or_none() is None:
        raise ValueError("Source node not found or not owned by user")

    fragment = SourceFragment(
        source_node_id=source_node_id,
        fragment_text=fragment_text,
        position=position,
        fragment_type=fragment_type,
        section_ref=section_ref,
    )
    db.add(fragment)
    await db.flush()

    # Generate embedding for fragment
    embedding = await generate_embedding(fragment_text)
    if embedding:
        fragment.embedding = embedding
        await db.flush()

    return fragment


async def list_fragments(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source_node_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[SourceFragment], int]:
    """List fragments for a source item, enforcing ownership."""
    # Verify source ownership
    source_node = await db.execute(
        select(Node).where(
            Node.id == source_node_id,
            Node.owner_id == owner_id,
            Node.type == NodeType.SOURCE_ITEM,
        )
    )
    if source_node.scalar_one_or_none() is None:
        raise ValueError("Source node not found or not owned by user")

    count_stmt = (
        select(func.count())
        .select_from(SourceFragment)
        .where(SourceFragment.source_node_id == source_node_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(SourceFragment)
        .where(SourceFragment.source_node_id == source_node_id)
        .order_by(SourceFragment.position.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    fragments = list(result.scalars().all())

    return fragments, total
