"""
Cleanup system router (Section 8.3).
Endpoints:
- GET /api/cleanup/queue  (Derived layer — computed at query time)
- POST /api/cleanup/action (Behavioral layer — executes cleanup actions)

Section 5.6: Cleanup System
- One-click actions: Archive, Snooze (with date), Convert, Reassign
- Batch operations: Review multiple stale items
- Review queues: Stale Tasks, Inactive Goals, Unprocessed Sources, Low-signal KB
  5-10 items per session, <90 second sessions.

Invariant D-01: All stale flags use DerivedExplanation.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.behavioral.cleanup_session import (
    assemble_cleanup_queue,
    cleanup_action_archive,
    cleanup_action_snooze,
    cleanup_action_keep,
)

router = APIRouter(prefix="/api/cleanup", tags=["cleanup"])


# =============================================================================
# Response schemas
# =============================================================================

class DerivedExplanationResponse(BaseModel):
    """
    Section 4.11: DerivedExplanation schema.
    Invariant D-01: Required for all user-facing Derived outputs.
    """
    summary: str
    factors: list[dict]  # [{signal, value, weight}]
    confidence: float | None = None
    generated_at: str | None = None
    version: str | None = None


class StaleItemResponse(BaseModel):
    node_id: str
    node_type: str
    title: str
    stale_category: str
    days_stale: int
    last_activity_at: str | None = None
    prompt: str
    explanation: DerivedExplanationResponse  # Invariant D-01
    snoozed_until: str | None = None
    metadata: dict = Field(default_factory=dict)


class CleanupQueueResponse(BaseModel):
    """
    Cleanup queue response.
    Section 5.6: 5-10 items per session.
    Invariant D-01: Every item includes DerivedExplanation.
    """
    items: list[StaleItemResponse]
    total_stale: int
    total_snoozed: int
    total_archived: int
    categories: dict[str, list[StaleItemResponse]]


class CleanupActionRequest(BaseModel):
    """
    Section 5.6: Cleanup action request.
    Supports batch operations on multiple nodes.
    """
    action: Literal["archive", "snooze", "keep"]
    node_ids: list[str]
    snoozed_until: datetime | None = None  # Required for "snooze" action


class CleanupActionResponse(BaseModel):
    action: str
    affected_node_ids: list[str]
    total_affected: int


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/queue", response_model=CleanupQueueResponse)
async def get_cleanup_queue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    category: str | None = Query(default=None, description="Filter by stale category"),
    limit: int = Query(default=10, ge=1, le=20, description="Max items (Section 5.6: 5-10 per session)"),
):
    """
    Get the cleanup queue.
    Layer: Derived (computed at query time from stale detection + snooze_records).

    Section 5.6: Review queues limited to 5-10 items per session.
    Visibility precedence: archived > snoozed > stale.
    Invariant D-01: Every item includes DerivedExplanation.
    """
    result = await assemble_cleanup_queue(db, user.id, category=category, limit=limit)

    def _stale_to_response(item) -> StaleItemResponse:
        return StaleItemResponse(
            node_id=str(item.node_id),
            node_type=item.node_type,
            title=item.title,
            stale_category=item.stale_category,
            days_stale=item.days_stale,
            last_activity_at=item.last_activity_at.isoformat() if item.last_activity_at else None,
            prompt=item.prompt,
            explanation=DerivedExplanationResponse(
                summary=item.explanation.summary,
                factors=[
                    {"signal": f.signal, "value": f.value, "weight": f.weight}
                    for f in item.explanation.factors
                ],
                confidence=item.explanation.confidence,
                generated_at=item.explanation.generated_at.isoformat() if item.explanation.generated_at else None,
                version=item.explanation.version,
            ),
            snoozed_until=item.snoozed_until.isoformat() if item.snoozed_until else None,
            metadata=item.metadata,
        )

    items = [_stale_to_response(item) for item in result.items]
    categories = {
        cat: [_stale_to_response(item) for item in cat_items]
        for cat, cat_items in result.categories.items()
    }

    return CleanupQueueResponse(
        items=items,
        total_stale=result.total_stale,
        total_snoozed=result.total_snoozed,
        total_archived=result.total_archived,
        categories=categories,
    )


@router.post("/action", response_model=CleanupActionResponse)
async def execute_cleanup_action(
    req: CleanupActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a cleanup action on one or more nodes.
    Layer: Behavioral (orchestrates Core state changes).

    Section 5.6: One-click actions: Archive, Snooze, Keep.
    Supports batch operations on stale items.
    """
    node_ids = [uuid.UUID(nid) for nid in req.node_ids]

    if req.action == "archive":
        affected = await cleanup_action_archive(db, user.id, node_ids)
    elif req.action == "snooze":
        if req.snoozed_until is None:
            raise HTTPException(status_code=400, detail="snoozed_until is required for snooze action")
        affected = await cleanup_action_snooze(db, user.id, node_ids, req.snoozed_until)
    elif req.action == "keep":
        affected = await cleanup_action_keep(db, user.id, node_ids)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    return CleanupActionResponse(
        action=req.action,
        affected_node_ids=[str(nid) for nid in affected],
        total_affected=len(affected),
    )
