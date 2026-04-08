"""
Cleanup session behavioral service (Section 5.6).
Orchestrates the cleanup workflow: stale detection + snooze filtering + queue assembly.

Section 5.6:
- One-click actions: Archive, Snooze (with date), Convert, Reassign
- Batch operations: Review multiple stale items
- Review queues: Stale Tasks, Inactive Goals, Unprocessed Sources, Low-signal KB
  Each limited to 5-10 items per session.
- Cleanup sessions: Quick loop (<60-90 seconds)

Visibility precedence (Section 1.6): archived > snoozed > stale.

Invariant D-01: All stale flags use DerivedExplanation.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node
from server.app.derived.stale_detection import (
    detect_all_stale,
    StaleItem,
)
from server.app.temporal.snooze_records import (
    create_snooze,
    get_snoozed_node_ids,
)

# Section 5.6: Review queues limited to 5-10 items per session
CLEANUP_QUEUE_MAX = 10
CLEANUP_QUEUE_TARGET = 5


@dataclass
class CleanupQueueResult:
    """Assembled cleanup queue after applying visibility precedence."""
    items: list[StaleItem]
    total_stale: int  # Total stale before snooze/archive filtering
    total_snoozed: int  # Items excluded by active snooze
    total_archived: int  # Items excluded by archived status (should be 0 since stale detection filters)
    categories: dict[str, list[StaleItem]]  # Grouped by stale_category


async def assemble_cleanup_queue(
    db: AsyncSession,
    owner_id: uuid.UUID,
    category: str | None = None,
    limit: int = CLEANUP_QUEUE_MAX,
) -> CleanupQueueResult:
    """
    Assemble the cleanup queue.
    Computed at query time from stale detection + snooze_records.

    Section 5.6: Review queues: 5-10 items per session.
    Visibility precedence: archived > snoozed > stale.

    Invariant D-01: Every item includes DerivedExplanation.
    """
    # Step 1: Detect all stale items (already excludes archived via archived_at IS NULL)
    all_stale = await detect_all_stale(db, owner_id)
    total_stale = len(all_stale)

    # Step 2: Visibility precedence — filter out snoozed items
    snoozed_ids = await get_snoozed_node_ids(db)
    total_snoozed = sum(1 for item in all_stale if item.node_id in snoozed_ids)

    # Apply snooze filter (archived already filtered by stale detection)
    visible_items = [item for item in all_stale if item.node_id not in snoozed_ids]

    # Step 3: Category filter if requested
    if category:
        visible_items = [item for item in visible_items if item.stale_category == category]

    # Step 4: Apply limit (Section 5.6: 5-10 items per session)
    limited_items = visible_items[:limit]

    # Step 5: Group by category
    categories: dict[str, list[StaleItem]] = {}
    for item in limited_items:
        categories.setdefault(item.stale_category, []).append(item)

    return CleanupQueueResult(
        items=limited_items,
        total_stale=total_stale,
        total_snoozed=total_snoozed,
        total_archived=0,
        categories=categories,
    )


async def cleanup_action_archive(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """
    Section 5.6: One-click action — Archive.
    Soft-delete by setting archived_at.
    Returns list of successfully archived node IDs.
    """
    archived = []
    now = datetime.now(timezone.utc)
    for node_id in node_ids:
        result = await db.execute(
            update(Node)
            .where(Node.id == node_id, Node.owner_id == owner_id, Node.archived_at.is_(None))
            .values(archived_at=now)
            .returning(Node.id)
        )
        row = result.scalar_one_or_none()
        if row:
            archived.append(row)
    return archived


async def cleanup_action_snooze(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_ids: list[uuid.UUID],
    snoozed_until: datetime,
) -> list[uuid.UUID]:
    """
    Section 5.6: One-click action — Snooze (with date).
    Creates snooze_records for each node.
    Returns list of successfully snoozed node IDs.
    """
    snoozed = []
    for node_id in node_ids:
        try:
            await create_snooze(db, owner_id, node_id, snoozed_until)
            snoozed.append(node_id)
        except ValueError:
            # Node not found or not owned — skip
            continue
    return snoozed


async def cleanup_action_keep(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """
    Section 5.6: "Keep" action — touch the node to reset staleness.
    Updates the updated_at timestamp to reset the stale clock.
    """
    kept = []
    now = datetime.now(timezone.utc)
    for node_id in node_ids:
        result = await db.execute(
            update(Node)
            .where(Node.id == node_id, Node.owner_id == owner_id)
            .values(updated_at=now)
            .returning(Node.id)
        )
        row = result.scalar_one_or_none()
        if row:
            kept.append(row)
    return kept


# =============================================================================
# Phase PB: Enhanced cleanup actions
# =============================================================================


async def cleanup_action_convert(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    target_type: str,
) -> dict:
    """
    Phase PB: Cleanup system enhancement — Convert action.
    Converts a stale node to a different type (e.g., stale task -> memory).

    This is effectively creating a new node of the target type and
    archiving the original, preserving the provenance link.
    """
    from server.app.core.models.enums import NodeType, EdgeRelationType, EdgeOrigin, MemoryType

    # Get original node
    from sqlalchemy import select as sa_select
    stmt = sa_select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(stmt)
    original = result.scalar_one_or_none()
    if original is None:
        raise ValueError(f"Node {node_id} not found or not owned by user")

    # Create new node of target type
    new_node = Node(
        type=NodeType(target_type),
        owner_id=owner_id,
        title=original.title,
        summary=original.summary,
    )
    db.add(new_node)
    await db.flush()

    # Create companion table record based on target type
    if target_type == "memory":
        from server.app.core.models.node import MemoryNode
        memory = MemoryNode(
            node_id=new_node.id,
            memory_type=MemoryType.LESSON,
            content=original.summary or original.title,
            tags=[],
        )
        db.add(memory)
        await db.flush()

    # Create provenance edge (semantic_reference from new to old)
    from server.app.core.models.edge import Edge
    edge = Edge(
        source_id=new_node.id,
        target_id=original.id,
        relation_type=EdgeRelationType.SEMANTIC_REFERENCE,
        origin=EdgeOrigin.SYSTEM,
    )
    db.add(edge)

    # Archive the original
    now = datetime.now(timezone.utc)
    original.archived_at = now

    await db.flush()

    return {
        "original_node_id": str(node_id),
        "new_node_id": str(new_node.id),
        "target_type": target_type,
        "archived_original": True,
    }


async def cleanup_action_reassign(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    target_project_id: uuid.UUID | None = None,
    target_goal_id: uuid.UUID | None = None,
) -> dict:
    """
    Phase PB: Cleanup system enhancement — Reassign action.
    Reassigns a stale node to a different project or goal.
    Creates belongs_to or goal_tracks_task edges as appropriate.
    """
    from server.app.core.models.enums import EdgeRelationType, EdgeOrigin, NodeType
    from server.app.core.models.edge import Edge
    from sqlalchemy import select as sa_select

    # Get original node
    stmt = sa_select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    result = await db.execute(stmt)
    original = result.scalar_one_or_none()
    if original is None:
        raise ValueError(f"Node {node_id} not found or not owned by user")

    edges_created = []
    now = datetime.now(timezone.utc)

    if target_project_id:
        # Verify project exists and is owned by user
        proj_stmt = sa_select(Node).where(
            Node.id == target_project_id,
            Node.owner_id == owner_id,
            Node.type == NodeType.PROJECT,
        )
        proj_result = await db.execute(proj_stmt)
        if proj_result.scalar_one_or_none() is None:
            raise ValueError(f"Project {target_project_id} not found")

        # Create belongs_to edge
        edge = Edge(
            source_id=node_id,
            target_id=target_project_id,
            relation_type=EdgeRelationType.BELONGS_TO,
            origin=EdgeOrigin.USER,
        )
        db.add(edge)
        edges_created.append(str(edge.id))

    if target_goal_id:
        # Verify goal exists and is owned by user
        goal_stmt = sa_select(Node).where(
            Node.id == target_goal_id,
            Node.owner_id == owner_id,
            Node.type == NodeType.GOAL,
        )
        goal_result = await db.execute(goal_stmt)
        if goal_result.scalar_one_or_none() is None:
            raise ValueError(f"Goal {target_goal_id} not found")

        # Create goal_tracks_task edge (goal -> task)
        if original.type == NodeType.TASK:
            edge = Edge(
                source_id=target_goal_id,
                target_id=node_id,
                relation_type=EdgeRelationType.GOAL_TRACKS_TASK,
                origin=EdgeOrigin.USER,
            )
            db.add(edge)
            edges_created.append(str(edge.id))

    # Touch the node to reset staleness
    original.updated_at = now
    await db.flush()

    return {
        "node_id": str(node_id),
        "target_project_id": str(target_project_id) if target_project_id else None,
        "target_goal_id": str(target_goal_id) if target_goal_id else None,
        "edges_created": edges_created,
    }
