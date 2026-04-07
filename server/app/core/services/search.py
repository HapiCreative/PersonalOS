"""
Search service — Phase 3: Hybrid search (full-text + vector similarity).
Ownership enforcement at query layer (Section 8.2).

Phase 1: Full-text search on nodes.title + summary using PostgreSQL tsvector.
Phase 3: Adds vector similarity search using pgvector cosine distance.
         Hybrid mode combines both scores with configurable weights.
"""

import uuid

from sqlalchemy import func, select, text, case, literal_column
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.services.embedding import generate_embedding


async def search_nodes(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
    mode: str | None = None,
) -> tuple[list[Node], int]:
    """
    Hybrid search on nodes (title + summary + embedding).
    Filters by owner_id for authorization (Section 8.2).
    Respects visibility precedence: archived items hidden by default (Section 1.6).

    Modes:
    - None / 'fulltext': Full-text search only (Phase 1 behavior)
    - 'vector': Vector similarity search only
    - 'hybrid': Combined full-text + vector similarity (default when embeddings exist)
    """
    if mode == "vector":
        return await _vector_search(db, owner_id, query, node_type, limit, offset, include_archived)
    elif mode == "hybrid":
        return await _hybrid_search(db, owner_id, query, node_type, limit, offset, include_archived)
    else:
        # Default: full-text search (backward compatible with Phase 1)
        return await _fulltext_search(db, owner_id, query, node_type, limit, offset, include_archived)


async def _fulltext_search(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
) -> tuple[list[Node], int]:
    """Full-text search using PostgreSQL tsvector (Phase 1 behavior)."""
    search_vector = func.to_tsvector(
        "english",
        func.coalesce(Node.title, "") + " " + func.coalesce(Node.summary, ""),
    )
    ts_query = func.plainto_tsquery("english", query)

    base_filter = [
        Node.owner_id == owner_id,
        search_vector.op("@@")(ts_query),
    ]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if node_type:
        base_filter.append(Node.type == node_type)

    count_stmt = select(func.count()).select_from(Node).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar_one()

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


async def _vector_search(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
) -> tuple[list[Node], int]:
    """Vector similarity search using pgvector cosine distance."""
    # Generate query embedding
    query_embedding = await generate_embedding(query)
    if query_embedding is None:
        # Fall back to full-text if embedding provider unavailable
        return await _fulltext_search(db, owner_id, query, node_type, limit, offset, include_archived)

    base_filter = [
        Node.owner_id == owner_id,
        Node.embedding.isnot(None),
    ]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if node_type:
        base_filter.append(Node.type == node_type)

    count_stmt = select(func.count()).select_from(Node).where(*base_filter)
    total = (await db.execute(count_stmt)).scalar_one()

    # Order by cosine distance (smaller = more similar)
    distance = Node.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Node)
        .where(*base_filter)
        .order_by(distance)
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return nodes, total


async def _hybrid_search(
    db: AsyncSession,
    owner_id: uuid.UUID,
    query: str,
    node_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
    fulltext_weight: float = 0.4,
    vector_weight: float = 0.6,
) -> tuple[list[Node], int]:
    """
    Hybrid search combining full-text ranking and vector similarity.
    Uses Reciprocal Rank Fusion (RRF) to merge scores from both methods.
    """
    query_embedding = await generate_embedding(query)

    # If no embedding available, fall back to full-text
    if query_embedding is None:
        return await _fulltext_search(db, owner_id, query, node_type, limit, offset, include_archived)

    search_vector = func.to_tsvector(
        "english",
        func.coalesce(Node.title, "") + " " + func.coalesce(Node.summary, ""),
    )
    ts_query = func.plainto_tsquery("english", query)
    ts_rank = func.ts_rank(search_vector, ts_query)

    # Cosine similarity (1 - cosine_distance)
    cosine_sim = (1.0 - Node.embedding.cosine_distance(query_embedding))

    # Combined score: weighted sum of full-text rank and cosine similarity
    # Use CASE to handle NULL embeddings (fall back to fulltext only)
    combined_score = (
        fulltext_weight * ts_rank +
        vector_weight * func.coalesce(cosine_sim, 0.0)
    )

    base_filter = [Node.owner_id == owner_id]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if node_type:
        base_filter.append(Node.type == node_type)

    # For hybrid search, include nodes that match either fulltext OR have embeddings
    # Fulltext match OR has embedding with reasonable similarity
    search_filter = base_filter + [
        (search_vector.op("@@")(ts_query)) | (Node.embedding.isnot(None))
    ]

    count_stmt = select(func.count()).select_from(Node).where(*search_filter)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node)
        .where(*search_filter)
        .order_by(combined_score.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    return nodes, total
