"""
Phase 10: Batch embedding service.
Efficiently generates embeddings for multiple nodes in batches.
Section 7: LLM Pipeline — embedding is a pipeline job type.
Invariant S-01: embedding on nodes = CACHED DERIVED.
Invariant D-02: Recomputable from Core content.
"""

import uuid
import logging
from dataclasses import dataclass

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, SourceFragment
from server.app.core.services.embedding import generate_embeddings

logger = logging.getLogger(__name__)

# Maximum batch size for embedding API calls
BATCH_SIZE = 50


@dataclass
class BatchEmbeddingResult:
    """Result of a batch embedding operation."""
    total_processed: int
    total_embedded: int
    total_skipped: int
    total_errors: int
    node_ids_embedded: list[str]


async def batch_embed_nodes(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_ids: list[uuid.UUID] | None = None,
    force_recompute: bool = False,
    limit: int = 200,
) -> BatchEmbeddingResult:
    """
    Generate embeddings for nodes in batches.
    Invariant S-01: embedding is CACHED DERIVED — recomputable.

    Args:
        db: Database session
        owner_id: Owner for authorization scope (B-04)
        node_ids: Specific nodes to embed. If None, processes all unembedded nodes.
        force_recompute: If True, recompute even if embedding exists.
        limit: Maximum number of nodes to process.
    """
    # Build query for nodes needing embedding
    filters = [
        Node.owner_id == owner_id,
        Node.archived_at.is_(None),
    ]

    if node_ids:
        filters.append(Node.id.in_(node_ids))

    if not force_recompute:
        filters.append(Node.embedding.is_(None))

    stmt = (
        select(Node)
        .where(*filters)
        .order_by(Node.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    nodes = list(result.scalars().all())

    if not nodes:
        return BatchEmbeddingResult(0, 0, 0, 0, [])

    total_processed = 0
    total_embedded = 0
    total_skipped = 0
    total_errors = 0
    embedded_ids: list[str] = []

    # Process in batches
    for i in range(0, len(nodes), BATCH_SIZE):
        batch = nodes[i:i + BATCH_SIZE]
        texts = []

        for node in batch:
            text = _build_embedding_text(node)
            if not text:
                total_skipped += 1
                continue
            texts.append(text)

        if not texts:
            continue

        try:
            embeddings = await generate_embeddings(texts)

            text_idx = 0
            for node in batch:
                text = _build_embedding_text(node)
                if not text:
                    continue

                if text_idx < len(embeddings) and embeddings[text_idx] is not None:
                    node.embedding = embeddings[text_idx]
                    total_embedded += 1
                    embedded_ids.append(str(node.id))
                else:
                    total_skipped += 1

                text_idx += 1
                total_processed += 1

            await db.flush()
        except Exception:
            logger.exception("Batch embedding failed for batch starting at index %d", i)
            total_errors += len(batch)

    return BatchEmbeddingResult(
        total_processed=total_processed,
        total_embedded=total_embedded,
        total_skipped=total_skipped,
        total_errors=total_errors,
        node_ids_embedded=embedded_ids,
    )


async def batch_embed_fragments(
    db: AsyncSession,
    source_node_id: uuid.UUID,
    force_recompute: bool = False,
) -> BatchEmbeddingResult:
    """
    Generate embeddings for source fragments in batches.
    Invariant S-01: fragment embedding is CACHED DERIVED.
    """
    filters = [SourceFragment.source_node_id == source_node_id]
    if not force_recompute:
        filters.append(SourceFragment.embedding.is_(None))

    stmt = (
        select(SourceFragment)
        .where(*filters)
        .order_by(SourceFragment.position)
    )
    result = await db.execute(stmt)
    fragments = list(result.scalars().all())

    if not fragments:
        return BatchEmbeddingResult(0, 0, 0, 0, [])

    texts = [f.fragment_text for f in fragments if f.fragment_text]
    if not texts:
        return BatchEmbeddingResult(len(fragments), 0, len(fragments), 0, [])

    total_embedded = 0
    total_errors = 0
    embedded_ids: list[str] = []

    for i in range(0, len(fragments), BATCH_SIZE):
        batch_frags = fragments[i:i + BATCH_SIZE]
        batch_texts = [f.fragment_text for f in batch_frags if f.fragment_text]

        try:
            embeddings = await generate_embeddings(batch_texts)
            text_idx = 0
            for frag in batch_frags:
                if not frag.fragment_text:
                    continue
                if text_idx < len(embeddings) and embeddings[text_idx] is not None:
                    frag.embedding = embeddings[text_idx]
                    total_embedded += 1
                    embedded_ids.append(str(frag.id))
                text_idx += 1

            await db.flush()
        except Exception:
            logger.exception("Fragment batch embedding failed")
            total_errors += len(batch_frags)

    return BatchEmbeddingResult(
        total_processed=len(fragments),
        total_embedded=total_embedded,
        total_skipped=len(fragments) - total_embedded - total_errors,
        total_errors=total_errors,
        node_ids_embedded=embedded_ids,
    )


def _build_embedding_text(node: Node) -> str:
    """Build the text for embedding from a node's title and summary."""
    parts = []
    if node.title:
        parts.append(node.title)
    if node.summary:
        parts.append(node.summary)
    return " ".join(parts).strip()
