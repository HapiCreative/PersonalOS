"""
Source promotion workflow (Section 6: Stage 4).

Invariants enforced:
- B-01: Promotion contract (derived_from_source edge auto-created, original unchanged)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    EdgeOrigin, EdgeRelationType, EdgeState, MemoryType,
    NodeType, TaskPriority, TaskStatus, TriageStatus,
)
from server.app.core.models.node import KBNode, MemoryNode, Node, TaskNode

from server.app.domains.sources.services.sources import get_source


async def promote_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source_node_id: uuid.UUID,
    target_type: str,
    title: str | None = None,
    memory_type: str | None = None,
    priority: str | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """
    Promote a source item to a knowledge entity.

    Invariant B-01: Promotion contract:
    - derived_from_source edge auto-created
    - Original source unchanged (copies, never moves)
    - Source triage_status -> promoted
    - Idempotent: re-promoting creates a new target each time
    """
    pair = await get_source(db, owner_id, source_node_id, update_accessed=False)
    if pair is None:
        raise ValueError("Source not found")

    source_node, source = pair
    promoted_title = title or source_node.title
    content = source.canonical_content or source.raw_content

    # Create the target node based on type
    if target_type == "kb_entry":
        target_node = Node(
            type=NodeType.KB_ENTRY,
            owner_id=owner_id,
            title=promoted_title,
            summary=source_node.summary,
        )
        db.add(target_node)
        await db.flush()

        kb = KBNode(
            node_id=target_node.id,
            content=content,
            raw_content=source.raw_content,
        )
        db.add(kb)
        await db.flush()

    elif target_type == "task":
        target_node = Node(
            type=NodeType.TASK,
            owner_id=owner_id,
            title=promoted_title,
            summary=source_node.summary,
        )
        db.add(target_node)
        await db.flush()

        task = TaskNode(
            node_id=target_node.id,
            status=TaskStatus.TODO,
            priority=TaskPriority(priority) if priority else TaskPriority.MEDIUM,
            notes=content[:500] if content else None,
        )
        db.add(task)
        await db.flush()

    elif target_type == "memory":
        target_node = Node(
            type=NodeType.MEMORY,
            owner_id=owner_id,
            title=promoted_title,
            summary=source_node.summary,
        )
        db.add(target_node)
        await db.flush()

        mem = MemoryNode(
            node_id=target_node.id,
            memory_type=MemoryType(memory_type) if memory_type else MemoryType.INSIGHT,
            content=content,
            context=source.capture_context,
        )
        db.add(mem)
        await db.flush()

    else:
        raise ValueError(f"Invalid target_type: {target_type}. Must be kb_entry, task, or memory.")

    # Invariant B-01: Auto-create derived_from_source edge
    edge = Edge(
        source_id=target_node.id,
        target_id=source_node.id,
        relation_type=EdgeRelationType.DERIVED_FROM_SOURCE,
        origin=EdgeOrigin.SYSTEM,
        state=EdgeState.ACTIVE,
        weight=1.0,
        metadata_={"promotion": True, "promoted_at": datetime.now(timezone.utc).isoformat()},
    )
    db.add(edge)
    await db.flush()

    # Invariant B-01: Update source triage_status to promoted
    source.triage_status = TriageStatus.PROMOTED
    await db.flush()

    # Copy embedding to target if available
    if source_node.embedding is not None:
        target_node.embedding = source_node.embedding
        await db.flush()

    return target_node.id, edge.id
