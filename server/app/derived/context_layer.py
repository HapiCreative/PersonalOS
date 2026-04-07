"""
Context layer service (Section 4, 9.1 — Derived Layer).

Memory retrieval context layer with 2-stage approach:
- Stage 1: Explicit links via graph traversal (highest confidence, unlabeled)
- Stage 2: Suggested links via embedding similarity (thresholded, 2-3 items max, labeled "Suggested")

Never mixed. One-click promotion from suggested to explicit link.

Context layer priority order (Section 9.1):
1. Backlinks (grouped by relation type)
2. Outgoing links (weight indicators for goals)
3. Provenance / supporting sources
4. Review status / habit signals / activity
5. AI suggestions (pending edges, max 2)
6. Resurfaced content (max 2)
7. Decay flags (max 1)

Invariant U-03: Hard cap of 8 items, target 5-8.
Invariant U-04: Per-section caps within context layer.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    EdgeRelationType, EdgeOrigin, EdgeState, NodeType,
)
from server.app.core.services.embedding import generate_embedding
from server.app.derived.models import SignalScore

# Invariant U-03: Context layer hard cap
CONTEXT_LAYER_HARD_CAP = 8
CONTEXT_LAYER_TARGET_MIN = 5

# Per-category caps within the context layer (Invariant U-04)
CATEGORY_CAPS = {
    "backlinks": 4,
    "outgoing_links": 3,
    "provenance": 2,
    "review_status": 2,
    "ai_suggestions": 2,
    "resurfaced": 2,
    "decay_flags": 1,
}

# Embedding similarity threshold for suggested links
SIMILARITY_THRESHOLD = 0.75
MAX_SUGGESTED = 3


@dataclass
class ContextItem:
    """A single item in the context layer."""
    category: str  # backlinks, outgoing_links, provenance, review_status, ai_suggestions, resurfaced, decay_flags
    node_id: uuid.UUID
    node_type: str
    title: str
    relation_type: str | None = None
    edge_id: str | None = None
    weight: float | None = None
    confidence: float | None = None
    is_suggested: bool = False
    label: str | None = None  # "Suggested" for Stage 2 items
    signal_score: float | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ContextLayerResult:
    """The assembled context layer for a node."""
    items: list[ContextItem]
    total_count: int
    categories: dict[str, list[ContextItem]]
    node_id: uuid.UUID
    suppression_applied: bool = False


async def _get_backlinks(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ContextItem]:
    """
    Stage 1: Get incoming edges (backlinks) grouped by relation type.
    These are explicit links — highest confidence, unlabeled.
    """
    stmt = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.source_id)
        .where(
            Edge.target_id == node_id,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.created_at.desc())
        .limit(CATEGORY_CAPS["backlinks"] * 2)  # Fetch extra, cap later
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for edge, source_node in rows:
        items.append(ContextItem(
            category="backlinks",
            node_id=source_node.id,
            node_type=source_node.type.value,
            title=source_node.title,
            relation_type=edge.relation_type.value,
            edge_id=str(edge.id),
            weight=edge.weight,
            confidence=edge.confidence,
            is_suggested=False,
        ))

    return items[:CATEGORY_CAPS["backlinks"]]


async def _get_outgoing_links(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ContextItem]:
    """
    Stage 1: Get outgoing edges with weight indicators.
    Especially important for goals (goal_tracks_task edges).
    """
    stmt = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.target_id)
        .where(
            Edge.source_id == node_id,
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.weight.desc(), Edge.created_at.desc())
        .limit(CATEGORY_CAPS["outgoing_links"] * 2)
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for edge, target_node in rows:
        items.append(ContextItem(
            category="outgoing_links",
            node_id=target_node.id,
            node_type=target_node.type.value,
            title=target_node.title,
            relation_type=edge.relation_type.value,
            edge_id=str(edge.id),
            weight=edge.weight,
            confidence=edge.confidence,
            is_suggested=False,
        ))

    return items[:CATEGORY_CAPS["outgoing_links"]]


async def _get_provenance(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ContextItem]:
    """
    Get provenance / supporting sources via derived_from_source edges.
    These show where the node's content originated.
    """
    provenance_types = [
        EdgeRelationType.DERIVED_FROM_SOURCE,
        EdgeRelationType.SOURCE_QUOTED_IN,
        EdgeRelationType.SOURCE_SUPPORTS_GOAL,
    ]

    # Check both directions for provenance
    stmt = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.source_id)
        .where(
            Edge.target_id == node_id,
            Edge.relation_type.in_(provenance_types),
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.created_at.desc())
        .limit(CATEGORY_CAPS["provenance"])
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    # Also check outgoing provenance (this node derived from source)
    stmt2 = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.target_id)
        .where(
            Edge.source_id == node_id,
            Edge.relation_type.in_(provenance_types),
            Edge.state == EdgeState.ACTIVE,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.created_at.desc())
        .limit(CATEGORY_CAPS["provenance"])
    )
    result2 = await db.execute(stmt2)
    rows.extend(result2.all())

    items = []
    seen_ids = set()
    for edge, linked_node in rows:
        if linked_node.id in seen_ids:
            continue
        seen_ids.add(linked_node.id)
        items.append(ContextItem(
            category="provenance",
            node_id=linked_node.id,
            node_type=linked_node.type.value,
            title=linked_node.title,
            relation_type=edge.relation_type.value,
            edge_id=str(edge.id),
            is_suggested=False,
        ))

    return items[:CATEGORY_CAPS["provenance"]]


async def _get_ai_suggestions(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ContextItem]:
    """
    Get pending AI-suggested edges (origin=llm, state=pending_review).
    These are from Stage 2 or LLM link suggestions.
    Invariant U-03/U-04: Max 2 AI suggestions in context layer.
    """
    stmt = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.target_id)
        .where(
            Edge.source_id == node_id,
            Edge.origin == EdgeOrigin.LLM,
            Edge.state == EdgeState.PENDING_REVIEW,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.confidence.desc().nullslast())
        .limit(CATEGORY_CAPS["ai_suggestions"])
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    # Also check incoming LLM suggestions
    stmt2 = (
        select(Edge, Node)
        .join(Node, Node.id == Edge.source_id)
        .where(
            Edge.target_id == node_id,
            Edge.origin == EdgeOrigin.LLM,
            Edge.state == EdgeState.PENDING_REVIEW,
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
        )
        .order_by(Edge.confidence.desc().nullslast())
        .limit(CATEGORY_CAPS["ai_suggestions"])
    )
    result2 = await db.execute(stmt2)
    rows.extend(result2.all())

    items = []
    seen_ids = set()
    for edge, linked_node in rows:
        if linked_node.id in seen_ids:
            continue
        seen_ids.add(linked_node.id)
        items.append(ContextItem(
            category="ai_suggestions",
            node_id=linked_node.id,
            node_type=linked_node.type.value,
            title=linked_node.title,
            relation_type=edge.relation_type.value,
            edge_id=str(edge.id),
            confidence=edge.confidence,
            is_suggested=True,
            label="Suggested",
            metadata=edge.metadata_ or {},
        ))

    return items[:CATEGORY_CAPS["ai_suggestions"]]


async def _get_suggested_by_embedding(
    db: AsyncSession,
    node_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> list[ContextItem]:
    """
    Stage 2: Suggested links via embedding similarity.
    Thresholded at SIMILARITY_THRESHOLD, max MAX_SUGGESTED items.
    Labeled "Suggested", one-click promotion to explicit link.
    """
    # Get the source node's embedding
    node_stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(node_stmt)
    node = result.scalar_one_or_none()
    if node is None or node.embedding is None:
        return []

    # Get existing linked node IDs to exclude
    existing_linked = set()
    edge_stmt = select(Edge.source_id, Edge.target_id).where(
        or_(Edge.source_id == node_id, Edge.target_id == node_id),
    )
    edge_result = await db.execute(edge_stmt)
    for src, tgt in edge_result.all():
        existing_linked.add(src)
        existing_linked.add(tgt)
    existing_linked.discard(node_id)

    # Find similar nodes by embedding
    distance = Node.embedding.cosine_distance(node.embedding)
    similarity = (1.0 - distance)

    stmt = (
        select(Node, similarity.label("sim"))
        .where(
            Node.owner_id == owner_id,
            Node.id != node_id,
            Node.archived_at.is_(None),
            Node.embedding.isnot(None),
        )
        .order_by(distance)
        .limit(MAX_SUGGESTED + len(existing_linked))  # Extra to account for filtering
    )
    result = await db.execute(stmt)
    rows = list(result.all())

    items = []
    for row_node, sim in rows:
        if row_node.id in existing_linked:
            continue
        if sim < SIMILARITY_THRESHOLD:
            continue
        if len(items) >= MAX_SUGGESTED:
            break

        items.append(ContextItem(
            category="resurfaced",
            node_id=row_node.id,
            node_type=row_node.type.value,
            title=row_node.title,
            is_suggested=True,
            label="Suggested",
            metadata={"similarity": round(float(sim), 3)},
        ))

    return items[:CATEGORY_CAPS["resurfaced"]]


async def assemble_context_layer(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> ContextLayerResult:
    """
    Assemble the full context layer for a node.

    Priority order (Section 9.1):
    1. Backlinks (grouped by relation type)
    2. Outgoing links (weight indicators for goals)
    3. Provenance / supporting sources
    4. Review status / habit signals / activity (future phases)
    5. AI suggestions (pending edges, max 2)
    6. Resurfaced content (max 2) — via embedding similarity
    7. Decay flags (max 1) — future phases

    Invariant U-03: Hard cap of 8 items, target 5-8.
    Invariant U-04: Per-category caps.
    """
    # Gather items from all categories (Stage 1: explicit links)
    backlinks = await _get_backlinks(db, node_id, owner_id)
    outgoing = await _get_outgoing_links(db, node_id, owner_id)
    provenance = await _get_provenance(db, node_id, owner_id)
    ai_suggestions = await _get_ai_suggestions(db, node_id, owner_id)

    # Stage 2: suggested links via embedding similarity
    suggested = await _get_suggested_by_embedding(db, node_id, owner_id)

    # Build categories dict
    categories: dict[str, list[ContextItem]] = {
        "backlinks": backlinks,
        "outgoing_links": outgoing,
        "provenance": provenance,
        "ai_suggestions": ai_suggestions,
        "resurfaced": suggested,
    }

    # Invariant U-03: Suppression rules
    # If backlinks + outgoing fill 6+, suppress AI/resurfacing
    suppression_applied = False
    explicit_count = len(backlinks) + len(outgoing) + len(provenance)
    if explicit_count >= 6:
        categories["ai_suggestions"] = []
        categories["resurfaced"] = []
        suppression_applied = True

    # Assemble in priority order
    priority_order = [
        "backlinks",
        "outgoing_links",
        "provenance",
        "review_status",
        "ai_suggestions",
        "resurfaced",
        "decay_flags",
    ]

    all_items: list[ContextItem] = []
    for cat_name in priority_order:
        all_items.extend(categories.get(cat_name, []))

    # Invariant U-03: Hard cap of 8 items
    all_items = all_items[:CONTEXT_LAYER_HARD_CAP]

    # Rebuild categories from capped items
    final_categories: dict[str, list[ContextItem]] = {}
    for item in all_items:
        final_categories.setdefault(item.category, []).append(item)

    # Enrich with signal scores
    node_ids = [item.node_id for item in all_items]
    if node_ids:
        score_stmt = select(SignalScore).where(SignalScore.node_id.in_(node_ids))
        score_result = await db.execute(score_stmt)
        scores = {s.node_id: s for s in score_result.scalars().all()}
        for item in all_items:
            ss = scores.get(item.node_id)
            if ss:
                item.signal_score = ss.score

    return ContextLayerResult(
        items=all_items,
        total_count=len(all_items),
        categories=final_categories,
        node_id=node_id,
        suppression_applied=suppression_applied,
    )
