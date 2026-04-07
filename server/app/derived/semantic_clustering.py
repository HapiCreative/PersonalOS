"""
Semantic clustering service (Section 4.9 — Derived Layer).

Groups related nodes into auto-detected topic clusters using embedding similarity.
Uses a simple agglomerative approach:
1. Fetch all non-archived nodes with embeddings
2. Compute pairwise cosine similarity
3. Group nodes that exceed a similarity threshold
4. Label clusters based on member node titles
5. Compute cluster centroids and coherence scores

Invariant D-02: Fully recomputable from node embeddings.
Invariant D-03: Non-canonical — stored in semantic_clusters / semantic_cluster_members.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.core.models.enums import NodeType
from server.app.derived.models import SemanticCluster, SemanticClusterMember
from server.app.derived.schemas import DerivedExplanation, DerivedFactor

# Clustering parameters
SIMILARITY_THRESHOLD = 0.78  # Minimum similarity to be in same cluster
MIN_CLUSTER_SIZE = 2         # Minimum members for a valid cluster
MAX_CLUSTERS = 20            # Maximum clusters per user


@dataclass
class ClusterInfo:
    """Represents a detected semantic cluster."""
    cluster_id: uuid.UUID | None = None
    label: str = ""
    node_ids: list[uuid.UUID] = field(default_factory=list)
    node_titles: list[str] = field(default_factory=list)
    node_types: list[str] = field(default_factory=list)
    centroid: list[float] | None = None
    coherence_score: float = 0.0
    node_count: int = 0
    similarities: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cluster_id": str(self.cluster_id) if self.cluster_id else None,
            "label": self.label,
            "node_count": self.node_count,
            "coherence_score": round(self.coherence_score, 3),
            "members": [
                {"node_id": str(nid), "title": t, "type": nt, "similarity": round(s, 3)}
                for nid, t, nt, s in zip(
                    self.node_ids, self.node_titles, self.node_types, self.similarities
                )
            ],
        }


def _generate_cluster_label(titles: list[str]) -> str:
    """
    Generate a human-readable cluster label from member titles.
    Simple heuristic: use the most common meaningful words.
    """
    if not titles:
        return "Unnamed cluster"

    # Collect words from titles
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
        "both", "either", "neither", "each", "every", "all", "any", "few",
        "more", "most", "other", "some", "such", "no", "only", "own", "same",
        "than", "too", "very", "just", "about", "my", "your", "how", "what",
        "this", "that", "it", "its",
    }

    word_counts: dict[str, int] = defaultdict(int)
    for title in titles:
        words = title.lower().split()
        for word in words:
            clean = word.strip(".,!?;:()[]{}\"'-")
            if clean and len(clean) > 2 and clean not in stop_words:
                word_counts[clean] += 1

    if not word_counts:
        return titles[0][:50] if titles else "Unnamed cluster"

    # Pick top 2-3 most common words
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    label_words = [w for w, _ in sorted_words[:3]]
    return " / ".join(w.capitalize() for w in label_words)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    dot = np.dot(a_arr, b_arr)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _compute_clusters(
    embeddings: dict[uuid.UUID, list[float]],
    titles: dict[uuid.UUID, str],
    types: dict[uuid.UUID, str],
) -> list[ClusterInfo]:
    """
    Simple agglomerative clustering based on cosine similarity.
    Invariant D-02: Deterministic and recomputable from embeddings.
    """
    node_ids = list(embeddings.keys())
    n = len(node_ids)
    if n < MIN_CLUSTER_SIZE:
        return []

    # Build adjacency: which nodes are similar enough
    adjacency: dict[int, set[int]] = defaultdict(set)
    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(embeddings[node_ids[i]], embeddings[node_ids[j]])
            if sim >= SIMILARITY_THRESHOLD:
                adjacency[i].add(j)
                adjacency[j].add(i)

    # Find connected components (clusters)
    visited = set()
    raw_clusters: list[list[int]] = []

    for start in range(n):
        if start in visited:
            continue
        if not adjacency[start]:
            continue  # Isolated node
        # BFS
        component = []
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    queue.append(neighbor)
        if len(component) >= MIN_CLUSTER_SIZE:
            raw_clusters.append(component)

    # Build ClusterInfo objects
    clusters: list[ClusterInfo] = []
    for component in raw_clusters[:MAX_CLUSTERS]:
        member_ids = [node_ids[i] for i in component]
        member_titles = [titles[nid] for nid in member_ids]
        member_types = [types[nid] for nid in member_ids]
        member_embeddings = [embeddings[nid] for nid in member_ids]

        # Compute centroid
        centroid = np.mean(member_embeddings, axis=0).tolist()

        # Compute coherence (average similarity to centroid)
        sims = [_cosine_similarity(emb, centroid) for emb in member_embeddings]
        coherence = sum(sims) / len(sims) if sims else 0.0

        cluster = ClusterInfo(
            label=_generate_cluster_label(member_titles),
            node_ids=member_ids,
            node_titles=member_titles,
            node_types=member_types,
            centroid=centroid,
            coherence_score=coherence,
            node_count=len(member_ids),
            similarities=sims,
        )
        clusters.append(cluster)

    # Sort by coherence (tightest clusters first)
    clusters.sort(key=lambda c: c.coherence_score, reverse=True)
    return clusters


async def compute_semantic_clusters(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[ClusterInfo]:
    """
    Compute semantic clusters for all of a user's nodes with embeddings.
    Replaces existing clusters (full recomputation per Invariant D-02).
    """
    # Fetch all non-archived nodes with embeddings
    stmt = select(Node).where(
        Node.owner_id == user_id,
        Node.archived_at.is_(None),
        Node.embedding.isnot(None),
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    if len(nodes) < MIN_CLUSTER_SIZE:
        return []

    # Build lookup maps
    embeddings: dict[uuid.UUID, list[float]] = {}
    titles: dict[uuid.UUID, str] = {}
    types: dict[uuid.UUID, str] = {}

    for node in nodes:
        embeddings[node.id] = list(node.embedding)
        titles[node.id] = node.title
        types[node.id] = node.type.value

    # Compute clusters
    clusters = _compute_clusters(embeddings, titles, types)

    # Persist: delete old clusters, insert new
    # Delete old cluster members first (cascade), then clusters
    old_clusters_stmt = select(SemanticCluster.id).where(
        SemanticCluster.user_id == user_id
    )
    result = await db.execute(old_clusters_stmt)
    old_ids = [r[0] for r in result.all()]

    if old_ids:
        await db.execute(
            delete(SemanticClusterMember).where(
                SemanticClusterMember.cluster_id.in_(old_ids)
            )
        )
        await db.execute(
            delete(SemanticCluster).where(
                SemanticCluster.user_id == user_id
            )
        )

    now = datetime.now(timezone.utc)

    for cluster in clusters:
        db_cluster = SemanticCluster(
            user_id=user_id,
            label=cluster.label,
            centroid=cluster.centroid,
            node_count=cluster.node_count,
            coherence_score=cluster.coherence_score,
            computed_at=now,
        )
        db.add(db_cluster)
        await db.flush()
        cluster.cluster_id = db_cluster.id

        # Add members
        for nid, sim in zip(cluster.node_ids, cluster.similarities):
            member = SemanticClusterMember(
                cluster_id=db_cluster.id,
                node_id=nid,
                similarity=sim,
                computed_at=now,
            )
            db.add(member)

    await db.flush()
    return clusters


async def get_clusters(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[ClusterInfo]:
    """Get existing semantic clusters for a user."""
    stmt = select(SemanticCluster).where(
        SemanticCluster.user_id == user_id,
    ).order_by(SemanticCluster.coherence_score.desc())
    result = await db.execute(stmt)
    db_clusters = list(result.scalars().all())

    clusters = []
    for dbc in db_clusters:
        # Get members
        member_stmt = (
            select(SemanticClusterMember, Node)
            .join(Node, Node.id == SemanticClusterMember.node_id)
            .where(SemanticClusterMember.cluster_id == dbc.id)
            .order_by(SemanticClusterMember.similarity.desc())
        )
        result = await db.execute(member_stmt)
        members = list(result.all())

        cluster = ClusterInfo(
            cluster_id=dbc.id,
            label=dbc.label,
            node_ids=[m.node_id for m, n in members],
            node_titles=[n.title for m, n in members],
            node_types=[n.type.value for m, n in members],
            centroid=list(dbc.centroid) if dbc.centroid is not None else None,
            coherence_score=dbc.coherence_score,
            node_count=dbc.node_count,
            similarities=[m.similarity for m, n in members],
        )
        clusters.append(cluster)

    return clusters


async def get_node_cluster(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> ClusterInfo | None:
    """Get the cluster a specific node belongs to."""
    member_stmt = select(SemanticClusterMember).where(
        SemanticClusterMember.node_id == node_id,
    )
    result = await db.execute(member_stmt)
    membership = result.scalar_one_or_none()
    if membership is None:
        return None

    # Get the full cluster
    cluster_stmt = select(SemanticCluster).where(
        SemanticCluster.id == membership.cluster_id,
    )
    result = await db.execute(cluster_stmt)
    db_cluster = result.scalar_one_or_none()
    if db_cluster is None:
        return None

    # Get members
    member_all_stmt = (
        select(SemanticClusterMember, Node)
        .join(Node, Node.id == SemanticClusterMember.node_id)
        .where(SemanticClusterMember.cluster_id == db_cluster.id)
        .order_by(SemanticClusterMember.similarity.desc())
    )
    result = await db.execute(member_all_stmt)
    members = list(result.all())

    return ClusterInfo(
        cluster_id=db_cluster.id,
        label=db_cluster.label,
        node_ids=[m.node_id for m, n in members],
        node_titles=[n.title for m, n in members],
        node_types=[n.type.value for m, n in members],
        centroid=list(db_cluster.centroid) if db_cluster.centroid is not None else None,
        coherence_score=db_cluster.coherence_score,
        node_count=db_cluster.node_count,
        similarities=[m.similarity for m, n in members],
    )


async def get_cluster_peers(
    db: AsyncSession,
    node_id: uuid.UUID,
    limit: int = 5,
) -> list[dict]:
    """
    Get related nodes from the same cluster as the given node.
    Used by smart resurfacing (Section 4.10).
    """
    member_stmt = select(SemanticClusterMember).where(
        SemanticClusterMember.node_id == node_id,
    )
    result = await db.execute(member_stmt)
    membership = result.scalar_one_or_none()
    if membership is None:
        return []

    # Get other members from the same cluster
    peers_stmt = (
        select(SemanticClusterMember, Node)
        .join(Node, Node.id == SemanticClusterMember.node_id)
        .where(
            SemanticClusterMember.cluster_id == membership.cluster_id,
            SemanticClusterMember.node_id != node_id,
            Node.archived_at.is_(None),
        )
        .order_by(SemanticClusterMember.similarity.desc())
        .limit(limit)
    )
    result = await db.execute(peers_stmt)
    peers = list(result.all())

    return [
        {
            "node_id": str(n.id),
            "title": n.title,
            "node_type": n.type.value,
            "similarity": round(m.similarity, 3),
            "cluster_id": str(membership.cluster_id),
        }
        for m, n in peers
    ]
