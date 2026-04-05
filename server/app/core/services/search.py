"""
Full-text search service (Phase 1 — no embeddings yet).
Searches nodes by title and summary using PostgreSQL tsvector.
Ownership enforcement at query layer (Section 8.2).
"""

import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node


async def search_nodes(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
) -> tuple[list[Node], int]:
    """
    Full-text search on nodes (title + summary).
    Filters by owner_id for authorization (Section 8.2).
    Respects visibility precedence: archived items hidden by default (Section 1.6).
    """
    search_vector = func.to_tsvector(
        "english",
        func.coalesce(Node.title, "") + " " + func.coalesce(Node.summary, ""),
    )
    ts_query = func.plainto_tsquery("english", query)

    base_filter = [
        Node.owner_id == owner_id,
        search_vector.op("@@")(ts_query),
    ]

    # Visibility precedence: archived > snoozed > stale (Section 1.6)
    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))

    if node_type:
        base_filter.append(Node.type == node_type)

    # Count query
    count_stmt = select(func.count()).select_from(Node).where(*base_filter)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    # Results query with ranking
    ts_rank = func.ts_rank(search_vector, ts_query)
    stmt = (
        select(Node)
        .where(*base_filter)
        .order_by(ts_rank.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return nodes, total
