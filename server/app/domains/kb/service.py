"""
KB domain service (Section 2.4, Section 7, 8.1).
Handles KB entry CRUD and the 6-stage compilation pipeline.

Compilation pipeline: ingest -> parse -> compile -> review -> accept -> stale
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    CompileStatus, NodeType, PipelineStage,
)
from server.app.core.models.node import KBNode, Node
from server.app.core.services.embedding import generate_embedding


# Valid compile_status transitions for the 6-stage pipeline
COMPILE_TRANSITIONS: dict[CompileStatus, set[CompileStatus]] = {
    CompileStatus.INGEST: {CompileStatus.PARSE},
    CompileStatus.PARSE: {CompileStatus.COMPILE},
    CompileStatus.COMPILE: {CompileStatus.REVIEW},
    CompileStatus.REVIEW: {CompileStatus.ACCEPT, CompileStatus.COMPILE},  # reject sends back to compile
    CompileStatus.ACCEPT: {CompileStatus.STALE},
    CompileStatus.STALE: {CompileStatus.INGEST},  # re-compile cycle
}


async def create_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    summary: str | None = None,
    content: str = "",
    raw_content: str | None = None,
    tags: list[str] | None = None,
) -> tuple[Node, KBNode]:
    """Create a KB entry (Core node + kb_nodes companion)."""
    node = Node(
        type=NodeType.KB_ENTRY,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    kb = KBNode(
        node_id=node.id,
        content=content,
        raw_content=raw_content or content,
        tags=tags or [],
    )
    db.add(kb)
    await db.flush()

    # Generate embedding
    embed_text = f"{title} {content[:500]}"
    embedding = await generate_embedding(embed_text)
    if embedding:
        node.embedding = embedding
        await db.flush()

    return node, kb


async def get_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, KBNode] | None:
    """Get a KB entry by node ID, enforcing ownership."""
    stmt = (
        select(Node, KBNode)
        .join(KBNode, KBNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, kb = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, kb


async def list_kb_entries(
    db: AsyncSession,
    owner_id: uuid.UUID,
    compile_status: CompileStatus | None = None,
    pipeline_stage: PipelineStage | None = None,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, KBNode]], int]:
    """List KB entries with optional filters, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.KB_ENTRY]

    if not include_archived:
        base_filter.append(Node.archived_at.is_(None))
    if compile_status:
        base_filter.append(KBNode.compile_status == compile_status)
    if pipeline_stage:
        base_filter.append(KBNode.pipeline_stage == pipeline_stage)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(KBNode, KBNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, KBNode)
        .join(KBNode, KBNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = None,
    content: str | None = None,
    raw_content: str | None = None,
    tags: list[str] | None = None,
) -> tuple[Node, KBNode] | None:
    """Update KB entry fields, enforcing ownership."""
    pair = await get_kb_entry(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, kb = pair

    if title is not None:
        node.title = title
    if summary is not None:
        node.summary = summary
    if content is not None:
        kb.content = content
    if raw_content is not None:
        kb.raw_content = raw_content
    if tags is not None:
        kb.tags = tags

    await db.flush()

    # Re-generate embedding if content changed
    if content is not None or title is not None:
        embed_text = f"{node.title} {kb.content[:500]}"
        embedding = await generate_embedding(embed_text)
        if embedding:
            node.embedding = embedding
            await db.flush()

    return node, kb


async def compile_kb_entry(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    action: str,
) -> tuple[Node, KBNode]:
    """
    Advance the KB compilation pipeline.

    Actions:
    - 'compile': Start compilation (ingest->parse->compile->review automatically)
    - 'accept': Accept a reviewed draft (review->accept)
    - 'reject': Send back for re-compilation (review->compile)

    The 6-stage pipeline: ingest -> parse -> compile -> review -> accept -> stale
    """
    pair = await get_kb_entry(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        raise ValueError("KB entry not found")

    node, kb = pair

    if action == "compile":
        # Fast-forward through ingest->parse->compile->review
        # In a full implementation, each stage would invoke LLM pipeline jobs.
        # For Phase 3, we simulate the pipeline progression.
        if kb.compile_status in (CompileStatus.INGEST, CompileStatus.STALE):
            kb.compile_status = CompileStatus.REVIEW
            kb.pipeline_stage = PipelineStage.REVIEW
            kb.compile_version += 1
        elif kb.compile_status == CompileStatus.COMPILE:
            kb.compile_status = CompileStatus.REVIEW
            kb.pipeline_stage = PipelineStage.REVIEW
        else:
            raise ValueError(
                f"Cannot compile from status {kb.compile_status.value}. "
                f"Expected ingest, stale, or compile."
            )

    elif action == "accept":
        if kb.compile_status != CompileStatus.REVIEW:
            raise ValueError(
                f"Cannot accept from status {kb.compile_status.value}. "
                f"Must be in review status."
            )
        kb.compile_status = CompileStatus.ACCEPT
        kb.pipeline_stage = PipelineStage.ACCEPTED

    elif action == "reject":
        if kb.compile_status != CompileStatus.REVIEW:
            raise ValueError(
                f"Cannot reject from status {kb.compile_status.value}. "
                f"Must be in review status."
            )
        kb.compile_status = CompileStatus.COMPILE
        kb.pipeline_stage = PipelineStage.DRAFT

    else:
        raise ValueError(f"Invalid action: {action}. Must be compile, accept, or reject.")

    await db.flush()
    return node, kb
