"""
Focus sessions temporal service (Section 3, TABLE 25).
Timed work sessions linked to a task. Append-only temporal records.

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-02: Append-only (no deletes in application layer).
Invariant T-04: Ownership alignment (user_id must match task owner_id).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.temporal.models import FocusSession
from server.app.core.models.node import Node, TaskNode
from server.app.core.models.enums import NodeType


async def start_focus_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    task_id: uuid.UUID,
) -> FocusSession:
    """
    Start a new focus session for a task.

    Invariant T-04: Verifies task ownership.
    Only one active session (no ended_at) per user at a time.
    """
    # Invariant T-04: Verify task exists and is owned by user
    stmt = (
        select(Node)
        .join(TaskNode, TaskNode.node_id == Node.id)
        .where(
            Node.id == task_id,
            Node.owner_id == user_id,
            Node.type == NodeType.TASK,
            Node.archived_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise ValueError(f"Task {task_id} not found or not owned by user (Invariant T-04)")

    # End any existing active session for this user
    active_stmt = select(FocusSession).where(
        FocusSession.user_id == user_id,
        FocusSession.ended_at.is_(None),
    )
    active_result = await db.execute(active_stmt)
    active_session = active_result.scalar_one_or_none()
    if active_session is not None:
        now = datetime.now(timezone.utc)
        active_session.ended_at = now
        started = active_session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        active_session.duration = int((now - started).total_seconds())

    # Create new session
    session = FocusSession(
        user_id=user_id,
        task_id=task_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    return session


async def end_focus_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> FocusSession | None:
    """
    End an active focus session.
    Computes duration from started_at to now.
    """
    stmt = select(FocusSession).where(
        FocusSession.id == session_id,
        FocusSession.user_id == user_id,
        FocusSession.ended_at.is_(None),
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        return None

    now = datetime.now(timezone.utc)
    session.ended_at = now
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    session.duration = int((now - started).total_seconds())
    await db.flush()
    return session


async def get_active_focus_session(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> FocusSession | None:
    """Get the currently active focus session for a user (ended_at IS NULL)."""
    stmt = select(FocusSession).where(
        FocusSession.user_id == user_id,
        FocusSession.ended_at.is_(None),
    ).order_by(FocusSession.started_at.desc()).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_focus_session(
    db: AsyncSession,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
) -> FocusSession | None:
    """Get a focus session by ID, enforcing ownership."""
    stmt = select(FocusSession).where(
        FocusSession.id == session_id,
        FocusSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_focus_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FocusSession], int]:
    """
    List focus sessions for a user, most recent first.
    Optionally filter by task_id.
    """
    base_filter = [FocusSession.user_id == user_id]
    if task_id:
        base_filter.append(FocusSession.task_id == task_id)

    count_stmt = (
        select(func.count())
        .select_from(FocusSession)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(FocusSession)
        .where(*base_filter)
        .order_by(FocusSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    sessions = list(result.scalars().all())

    return sessions, total


async def get_focus_time_for_date(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_date: datetime,
) -> int:
    """Get total focus time in seconds for a specific date."""
    from datetime import timedelta

    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    stmt = (
        select(func.coalesce(func.sum(FocusSession.duration), 0))
        .where(
            FocusSession.user_id == user_id,
            FocusSession.started_at >= start_of_day,
            FocusSession.started_at < end_of_day,
            FocusSession.ended_at.isnot(None),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one()
