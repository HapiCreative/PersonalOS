"""
Memory contextual surfacing service (Phase PB).

Section 4.5: Memory retrieval context layer with 2-stage approach:
- Stage 1: Explicit links via graph traversal (highest confidence, unlabeled)
- Stage 2: Suggested links via embedding similarity (thresholded, 2-3 items max, labeled "Suggested")

Phase PB enhancement: Graph traversal first, embedding second.
This service provides memory-specific contextual surfacing that prioritizes
graph-connected memories over embedding-similar ones.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, MemoryNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, MemoryType, EdgeRelationType, EdgeState,
)

# Stage 2 thresholds
MEMORY_SIMILARITY_THRESHOLD = 0.75
MAX_SUGGESTED_MEMORIES = 3
MAX_EXPLICIT_MEMORIES = 5


@dataclass
class SurfacedMemory:
    """A memory surfaced via graph or embedding."""
    node_id: uuid.UUID
    title: str
    memory_type: str
    content_preview: str
    context: str | None
    review_at: datetime | None
    source: str  # "graph" or "embedding"
    relation_type: str | None = None
    edge_id: str | None = None
    similarity: float | None = None
    is_suggested: bool = False
    label: str | None = None  # "Suggested" for Stage 2
    tags: list[str] = field(default_factory=list)


@dataclass
class MemorySurfacingResult:
    """Combined result of memory surfacing."""
    explicit: list[SurfacedMemory]  # Stage 1: graph traversal
    suggested: list[SurfacedMemory]  # Stage 2: embedding similarity
    total_count: int
    node_id: uuid.UUID


async def _get_explicit_memories(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[SurfacedMemory]:
    """
    Stage 1: Get memories connected to this node via graph edges.
    Graph traversal first — highest confidence, unlabeled.
    """
    # Find memory nodes connected via edges in either direction
    # Outgoing edges from node to memory
    stmt_out = (
        select(Edge, Node, MemoryNode)
        .join(Node, Node.id == Edge.target_id)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(
            Edge.source_id == node_id,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.type == NodeType.MEMORY,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.weight.desc(), Edge.created_at.desc())
        .limit(MAX_EXPLICIT_MEMORIES)
    )
    result_out = await db.execute(stmt_out)
    rows_out = list(result_out.all())

    # Incoming edges from memory to node
    stmt_in = (
        select(Edge, Node, MemoryNode)
        .join(Node, Node.id == Edge.source_id)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(
            Edge.target_id == node_id,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.type == NodeType.MEMORY,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.weight.desc(), Edge.created_at.desc())
        .limit(MAX_EXPLICIT_MEMORIES)
    )
    result_in = await db.execute(stmt_in)
    rows_in = list(result_in.all())

    items: list[SurfacedMemory] = []
    seen_ids: set[uuid.UUID] = set()

    for edge, memory_node, memory in [*rows_out, *rows_in]:
        if memory_node.id in seen_ids:
            continue
        seen_ids.add(memory_node.id)
        items.append(SurfacedMemory(
            node_id=memory_node.id,
            title=memory_node.title,
            memory_type=memory.memory_type.value,
            content_preview=memory.content[:200] if memory.content else "",
            context=memory.context,
            review_at=memory.review_at,
            source="graph",
            relation_type=edge.relation_type.value,
            edge_id=str(edge.id),
            is_suggested=False,
            tags=memory.tags or [],
        ))

    return items[:MAX_EXPLICIT_MEMORIES]


async def _get_suggested_memories(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
    exclude_ids: set[uuid.UUID],
) -> list[SurfacedMemory]:
    """
    Stage 2: Get semantically similar memories via embedding.
    Thresholded, max MAX_SUGGESTED_MEMORIES items.
    Labeled "Suggested", one-click promotion to explicit link.
    """
    # Get the source node's embedding
    node_stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(node_stmt)
    node = result.scalar_one_or_none()
    if node is None or node.embedding is None:
        return []

    # Find similar memory nodes by embedding
    distance = Node.embedding.cosine_distance(node.embedding)
    similarity = (1.0 - distance)

    stmt = (
        select(Node, MemoryNode, similarity.label("sim"))
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.id != node_id,
            Node.type == NodeType.MEMORY,
            Node.archived_at.is_(None),
            Node.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(MAX_SUGGESTED_MEMORIES + len(exclude_ids) + 5)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items: list[SurfacedMemory] = []
    for memory_node, memory, sim in rows:
        if memory_node.id in exclude_ids:
            continue
        if sim < MEMORY_SIMILARITY_THRESHOLD:
            continue
        if len(items) >= MAX_SUGGESTED_MEMORIES:
            break

        items.append(SurfacedMemory(
            node_id=memory_node.id,
            title=memory_node.title,
            memory_type=memory.memory_type.value,
            content_preview=memory.content[:200] if memory.content else "",
            context=memory.context,
            review_at=memory.review_at,
            source="embedding",
            similarity=round(float(sim), 3),
            is_suggested=True,
            label="Suggested",
            tags=memory.tags or [],
        ))

    return items


async def surface_memories_for_node(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> MemorySurfacingResult:
    """
    Phase PB: Memory contextual surfacing.
    Graph traversal first, embedding second.

    Section 4.5:
    - Stage 1: Explicit links via graph traversal
    - Stage 2: Suggested links via embedding similarity
    - Never mix the two sections
    - User can promote a suggestion to explicit link with one click
    """
    # Stage 1: Graph traversal first (highest priority)
    explicit = await _get_explicit_memories(db, node_id, owner_id)

    # Collect IDs to exclude from Stage 2
    exclude_ids = {m.node_id for m in explicit}
    exclude_ids.add(node_id)

    # Stage 2: Embedding similarity (secondary)
    suggested = await _get_suggested_memories(db, node_id, owner_id, exclude_ids)

    return MemorySurfacingResult(
        explicit=explicit,
        suggested=suggested,
        total_count=len(explicit) + len(suggested),
        node_id=node_id,
    )
