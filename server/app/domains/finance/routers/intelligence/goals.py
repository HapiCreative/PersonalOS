"""Financial goal progress endpoints (Section 4.4)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.routers.intelligence._helpers import (
    explanation_to_response,
)
from server.app.domains.finance.schemas.derived import (
    GoalProgressListResponse,
    GoalProgressResponse,
)
from server.app.domains.finance.services.goal_progress import (
    compute_goal_progress,
    list_goal_progress,
)

router = APIRouter()


def _to_response(result: dict) -> GoalProgressResponse:
    return GoalProgressResponse(
        goal_id=result["goal_id"],
        goal_name=result["goal_name"],
        target_amount=result["target_amount"],
        current_amount=result["current_amount"],
        currency=result["currency"],
        progress_pct=result["progress_pct"],
        end_date=result["end_date"],
        days_remaining=result["days_remaining"],
        monthly_contribution_rate=result["monthly_contribution_rate"],
        projected_completion_date=result["projected_completion_date"],
        monthly_contribution_needed=result["monthly_contribution_needed"],
        is_on_track=result["is_on_track"],
        allocation_count=result["allocation_count"],
        explanation=explanation_to_response(result["explanation"]),
    )


@router.get("/goals", response_model=GoalProgressListResponse)
async def list_financial_goal_progress(
    as_of_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.4: Progress for every financial goal owned by user."""
    results = await list_goal_progress(db, user.id, as_of_date)
    return GoalProgressListResponse(goals=[_to_response(r) for r in results])


@router.get("/goals/{goal_id}", response_model=GoalProgressResponse)
async def get_financial_goal_progress(
    goal_id: uuid.UUID,
    as_of_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Section 4.4: Progress for a single financial goal."""
    result = await compute_goal_progress(db, user.id, goal_id, as_of_date)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Financial goal {goal_id} not found, not owned by user, "
                f"or not of goal_type=financial"
            ),
        )
    return _to_response(result)
