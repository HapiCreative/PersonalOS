"""
Goal progress refresh endpoint (Section 8.3).
Invariant D-03: progress is non-canonical, recomputable.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.goals.schemas import GoalResponse
from server.app.domains.goals.services import get_goal, refresh_goal_progress
from server.app.domains.goals.routers.goals import _to_response

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.post("/{node_id}/refresh-progress", response_model=GoalResponse)
async def refresh_progress_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually refresh goal progress computation.
    Invariant D-03: progress is non-canonical, recomputable.
    """
    pair = await get_goal(db, user.id, node_id, update_accessed=False)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    await refresh_goal_progress(db, node_id)
    pair = await get_goal(db, user.id, node_id, update_accessed=False)
    return _to_response(*pair)  # type: ignore
