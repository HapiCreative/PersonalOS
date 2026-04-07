"""
Snooze records temporal service (Section 3.5).
Manages snooze state for cleanup system (Section 5.6).

Visibility precedence (Section 1.6): archived > snoozed > stale.
Snoozed items are hidden from cleanup queues until snoozed_until expires.

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-04: Ownership alignment (joins through Core nodes).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.temporal.models import SnoozeRecord
from server.app.core.models.node import Node


async def create_snooze(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    snoozed_until: datetime,
) -> SnoozeRecord:
    """
    Snooze a node until a given date.
    Enforces ownership alignment (Invariant T-04).
    """
    # Invariant T-04: Verify the node belongs to the requesting user
    node = await db.execute(
        select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    )
    node_result = node.scalar_one_or_none()
    if node_result is None:
        raise ValueError(f"Node {node_id} not found or not owned by user")

    # Cancel any existing active snooze for this node
    await db.execute(
        delete(SnoozeRecord).where(
            SnoozeRecord.node_id == node_id,
            SnoozeRecord.snoozed_until > datetime.now(timezone.utc),
        )
    )

    record = SnoozeRecord(
        node_id=node_id,
        snoozed_until=snoozed_until,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.flush()
    return record


async def delete_snooze(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> bool:
    """
    Remove active snooze for a node (un-snooze).
    Invariant T-04: Ownership alignment.
    Returns True if a snooze was removed.
    """
    # Verify ownership
    node = await db.execute(
        select(Node).where(Node.id == node_id, Node.owner_id == owner_id)
    )
    if node.scalar_one_or_none() is None:
        raise ValueError(f"Node {node_id} not found or not owned by user")

    result = await db.execute(
        delete(SnoozeRecord).where(
            SnoozeRecord.node_id == node_id,
            SnoozeRecord.snoozed_until > datetime.now(timezone.utc),
        )
    )
    return result.rowcount > 0


async def get_active_snooze(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> SnoozeRecord | None:
    """Get the active snooze record for a node, if any."""
    result = await db.execute(
        select(SnoozeRecord).where(
            SnoozeRecord.node_id == node_id,
            SnoozeRecord.snoozed_until > datetime.now(timezone.utc),
        ).order_by(SnoozeRecord.snoozed_until.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def get_snoozed_node_ids(
    db: AsyncSession,
) -> set[uuid.UUID]:
    """Get all currently snoozed node IDs (snoozed_until > now)."""
    result = await db.execute(
        select(SnoozeRecord.node_id).where(
            SnoozeRecord.snoozed_until > datetime.now(timezone.utc),
        )
    )
    return {row[0] for row in result.all()}


async def get_snooze_records_for_nodes(
    db: AsyncSession,
    node_ids: list[uuid.UUID],
) -> dict[uuid.UUID, SnoozeRecord]:
    """Get active snooze records for a list of nodes."""
    if not node_ids:
        return {}
    result = await db.execute(
        select(SnoozeRecord).where(
            SnoozeRecord.node_id.in_(node_ids),
            SnoozeRecord.snoozed_until > datetime.now(timezone.utc),
        )
    )
    records = result.scalars().all()
    return {r.node_id: r for r in records}
