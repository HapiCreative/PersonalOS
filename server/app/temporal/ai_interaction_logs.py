"""
AI Interaction Logs — Temporal layer service (Section 3.6).
Logs all AI mode interactions for behavioral history.

Invariant T-01: No temporal-to-temporal FKs.
Invariant T-04: user_id must match owner_id of referenced nodes.
Invariant T-03: Records retained indefinitely; node_deleted flag on hard-delete.
"""

import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import AIInteractionLog
from server.app.core.models.enums import AIMode

logger = logging.getLogger(__name__)


async def log_interaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    mode: AIMode,
    query: str,
    response_summary: str | None = None,
    response_data: dict | None = None,
    context_node_ids: list[uuid.UUID] | None = None,
    duration_ms: int | None = None,
) -> AIInteractionLog:
    """
    Log an AI interaction.
    Invariant T-04: Caller must verify user_id matches owner_id of context nodes.
    """
    log_entry = AIInteractionLog(
        user_id=user_id,
        mode=mode,
        query=query,
        response_summary=response_summary,
        response_data=response_data or {},
        context_node_ids=context_node_ids or [],
        duration_ms=duration_ms,
    )
    db.add(log_entry)
    await db.flush()
    return log_entry


async def list_interactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    mode: AIMode | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AIInteractionLog], int]:
    """List AI interaction logs with ownership enforcement."""
    filters = [AIInteractionLog.user_id == user_id]
    if mode:
        filters.append(AIInteractionLog.mode == mode)

    count_stmt = select(func.count()).select_from(AIInteractionLog).where(*filters)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(AIInteractionLog)
        .where(*filters)
        .order_by(AIInteractionLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = list(result.scalars().all())

    return logs, total


async def get_recent_interactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    mode: AIMode | None = None,
    limit: int = 5,
) -> list[AIInteractionLog]:
    """Get recent interactions for context in AI modes."""
    filters = [AIInteractionLog.user_id == user_id]
    if mode:
        filters.append(AIInteractionLog.mode == mode)

    stmt = (
        select(AIInteractionLog)
        .where(*filters)
        .order_by(AIInteractionLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
