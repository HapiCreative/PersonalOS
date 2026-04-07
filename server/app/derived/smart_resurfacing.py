"""
Smart resurfacing service (Section 4.10 — Derived Layer).

Two modes of resurfacing:
1. Context layer (pull-based): 3-5 items, triggered on node open.
   Returns related nodes from the same semantic cluster or nearby in embedding space.
2. Today Mode (push-based): 1-2 items max, computed at daily load.
   Returns high-signal nodes the user hasn't seen recently.

Invariant D-02: Fully recomputable from Core + Derived data.
Invariant D-03: Non-canonical — never stored as source of truth.
Invariant U-01: Max 2 unsolicited intelligence items on any surface.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.models.edge import Edge
from server.app.core.models.enums import NodeType, EdgeState
from server.app.derived.models import SignalScore, SemanticClusterMember, SemanticCluster
from server.app.derived.schemas import DerivedExplanation, DerivedFactor

# Context layer resurfacing limits
CONTEXT_RESURFACE_MIN = 3
CONTEXT_RESURFACE_MAX = 5

# Today Mode resurfacing limits (Invariant U-01)
TODAY_RESURFACE_MAX = 2

# Recency threshold: don't resurface things accessed in last N days
RECENCY_COOLDOWN_DAYS = 7

# Minimum signal score for resurfacing
MIN_SIGNAL_SCORE = 0.3


@dataclass
class ResurfacedItem:
    """A single resurfaced content item."""
    node_id: uuid.UUID
    node_type: str
    title: str
    reason: str  # "same_cluster", "high_signal", "embedding_similar"
    signal_score: float | None = None
    similarity: float | None = None
    cluster_label: str | None = None
    explanation: DerivedExplanation | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": str(self.node_id),
            "node_type": self.node_type,
            "title": self.title,
            "reason": self.reason,
            "signal_score": self.signal_score,
            "similarity": self.similarity,
            "cluster_label": self.cluster_label,
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "metadata": self.metadata,
        }


async def resurface_for_context(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    limit: int = CONTEXT_RESURFACE_MAX,
) -> list[ResurfacedItem]:
    """
    Context layer resurfacing (pull-based).
    Triggered on node open. Returns 3-5 related items from the same cluster.

    Section 4.10: Context layer — pull-based, 3-5 items, triggered on node open.
    Invariant D-02: Recomputable from embeddings + clusters.
    """
    items: list[ResurfacedItem] = []

    # Get existing linked node IDs to exclude
    existing_linked = set()
    edge_stmt = select(Edge.source_id, Edge.target_id).where(
        or_(Edge.source_id == node_id, Edge.target_id == node_id),
        Edge.state == EdgeState.ACTIVE,
    )
    result = await db.execute(edge_stmt)
    for src, tgt in result.all():
        existing_linked.add(src)
        existing_linked.add(tgt)
    existing_linked.add(node_id)  # Exclude self

    # Strategy 1: Cluster peers (same semantic cluster)
    member_stmt = select(SemanticClusterMember).where(
        SemanticClusterMember.node_id == node_id,
    )
    result = await db.execute(member_stmt)
    membership = result.scalar_one_or_none()

    if membership is not None:
        # Get cluster info for label
        cluster_stmt = select(SemanticCluster).where(
            SemanticCluster.id == membership.cluster_id
        )
        result = await db.execute(cluster_stmt)
        cluster = result.scalar_one_or_none()
        cluster_label = cluster.label if cluster else None

        # Get cluster peers
        peers_stmt = (
            select(SemanticClusterMember, Node)
            .join(Node, Node.id == SemanticClusterMember.node_id)
            .where(
                SemanticClusterMember.cluster_id == membership.cluster_id,
                SemanticClusterMember.node_id != node_id,
                SemanticClusterMember.node_id.notin_(existing_linked),
                Node.owner_id == owner_id,
                Node.archived_at.is_(None),
            )
            .order_by(SemanticClusterMember.similarity.desc())
            .limit(limit)
        )
        result = await db.execute(peers_stmt)
        peers = list(result.all())

        for cm_member, peer_node in peers:
            items.append(ResurfacedItem(
                node_id=peer_node.id,
                node_type=peer_node.type.value,
                title=peer_node.title,
                reason="same_cluster",
                similarity=cm_member.similarity,
                cluster_label=cluster_label,
                explanation=DerivedExplanation(
                    summary=f"Related topic in cluster '{cluster_label}'",
                    factors=[
                        DerivedFactor(signal="cluster_similarity", value=round(cm_member.similarity, 3), weight=0.8),
                        DerivedFactor(signal="cluster_label", value=cluster_label or "", weight=0.2),
                    ],
                    generated_at=datetime.now(timezone.utc),
                    version="v1",
                ),
            ))

    # Strategy 2: Embedding similarity fallback (if not enough cluster peers)
    if len(items) < CONTEXT_RESURFACE_MIN:
        source_node_stmt = select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
        result = await db.execute(source_node_stmt)
        source_node = result.scalar_one_or_none()

        if source_node and source_node.embedding is not None:
            already_found = {item.node_id for item in items}
            exclude_ids = existing_linked | already_found

            distance = Node.embedding.cosine_distance(source_node.embedding)
            similarity_expr = (1.0 - distance)

            sim_stmt = (
                select(Node, similarity_expr.label("sim"))
                .where(
                    Node.owner_id == owner_id,
                    Node.id.notin_(exclude_ids),
                    Node.archived_at.is_(None),
                    Node.embedding.isnot(None),
                )
                .order_by(distance)
                .limit(limit - len(items) + 5)  # Extra for filtering
            )
            result = await db.execute(sim_stmt)
            for row_node, sim in result.all():
                if sim < 0.6:
                    continue
                if len(items) >= limit:
                    break
                items.append(ResurfacedItem(
                    node_id=row_node.id,
                    node_type=row_node.type.value,
                    title=row_node.title,
                    reason="embedding_similar",
                    similarity=float(sim),
                    explanation=DerivedExplanation(
                        summary=f"Semantically similar content (similarity: {sim:.0%})",
                        factors=[
                            DerivedFactor(signal="embedding_similarity", value=round(float(sim), 3), weight=1.0),
                        ],
                        generated_at=datetime.now(timezone.utc),
                        version="v1",
                    ),
                ))

    # Enrich with signal scores
    node_ids = [item.node_id for item in items]
    if node_ids:
        score_stmt = select(SignalScore).where(SignalScore.node_id.in_(node_ids))
        result = await db.execute(score_stmt)
        scores = {s.node_id: s for s in result.scalars().all()}
        for item in items:
            ss = scores.get(item.node_id)
            if ss:
                item.signal_score = ss.score

    return items[:limit]


async def resurface_for_today(
    db: AsyncSession,
    owner_id: uuid.UUID,
    limit: int = TODAY_RESURFACE_MAX,
) -> list[ResurfacedItem]:
    """
    Today Mode resurfacing (push-based).
    Returns 1-2 high-signal nodes the user hasn't seen recently.

    Section 4.10: Today Mode — push-based, 1-2 items max, daily load.
    Invariant U-01: Max 2 unsolicited intelligence items.
    Invariant D-02: Recomputable from signal scores + access timestamps.
    """
    now = datetime.now(timezone.utc)
    cooldown_cutoff = now - timedelta(days=RECENCY_COOLDOWN_DAYS)

    # Find high-signal nodes not recently accessed
    stmt = (
        select(Node, SignalScore)
        .join(SignalScore, SignalScore.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.archived_at.is_(None),
            SignalScore.score >= MIN_SIGNAL_SCORE,
            or_(
                Node.last_accessed_at.is_(None),
                Node.last_accessed_at < cooldown_cutoff,
            ),
        )
        .order_by(SignalScore.score.desc())
        .limit(limit * 3)  # Fetch extra for diversity
    )
    result = await db.execute(stmt)
    candidates = list(result.all())

    # Diversify: prefer different types
    items: list[ResurfacedItem] = []
    seen_types: set[str] = set()

    for node, score in candidates:
        if len(items) >= limit:
            break
        # Try to get one of each type first
        if node.type.value in seen_types and len(items) < limit - 1:
            continue
        seen_types.add(node.type.value)

        days_since = "never"
        if node.last_accessed_at:
            days = (now - node.last_accessed_at).days
            days_since = f"{days} days ago"

        items.append(ResurfacedItem(
            node_id=node.id,
            node_type=node.type.value,
            title=node.title,
            reason="high_signal",
            signal_score=score.score,
            explanation=DerivedExplanation(
                summary=f"High relevance score ({score.score:.0%}), last accessed {days_since}",
                factors=[
                    DerivedFactor(signal="signal_score", value=round(score.score, 3), weight=0.7),
                    DerivedFactor(
                        signal="days_since_access",
                        value=(now - node.last_accessed_at).days if node.last_accessed_at else -1,
                        weight=0.3,
                    ),
                ],
                generated_at=now,
                version="v1",
            ),
        ))

    # If diversity didn't fill the limit, fill from remaining candidates
    if len(items) < limit:
        used_ids = {item.node_id for item in items}
        for node, score in candidates:
            if len(items) >= limit:
                break
            if node.id in used_ids:
                continue
            days_since = "never"
            if node.last_accessed_at:
                days = (now - node.last_accessed_at).days
                days_since = f"{days} days ago"
            items.append(ResurfacedItem(
                node_id=node.id,
                node_type=node.type.value,
                title=node.title,
                reason="high_signal",
                signal_score=score.score,
                explanation=DerivedExplanation(
                    summary=f"High relevance score ({score.score:.0%}), last accessed {days_since}",
                    factors=[
                        DerivedFactor(signal="signal_score", value=round(score.score, 3), weight=0.7),
                        DerivedFactor(
                            signal="days_since_access",
                            value=(now - node.last_accessed_at).days if node.last_accessed_at else -1,
                            weight=0.3,
                        ),
                    ],
                    generated_at=now,
                    version="v1",
                ),
            ))

    return items
