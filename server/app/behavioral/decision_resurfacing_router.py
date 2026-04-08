"""
Decision resurfacing router (Phase PB — Behavioral layer).

Section 5.7: Decision resurfacing workflow.
Section 8.1: behavioral/ — decision resurfacing
Section 8.3: Layer-annotated API

Endpoint: GET /api/decisions/resurfacing
Layer: Behavioral + Derived (queries at load time)
"""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.behavioral.decision_resurfacing import (
    get_decisions_for_resurfacing,
    ResurfacedDecision,
)

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


class DerivedExplanationResponse(BaseModel):
    summary: str
    factors: list[dict]
    confidence: float | None = None
    generated_at: str | None = None
    version: str | None = None


class ResurfacedDecisionResponse(BaseModel):
    """A decision needing outcome evaluation."""
    node_id: str
    title: str
    content: str
    context: str | None = None
    review_at: str | None = None
    created_at: str
    resurfacing_reason: str
    days_since_creation: int
    has_outcome_edges: bool
    explanation: DerivedExplanationResponse
    tags: list[str] = Field(default_factory=list)


class DecisionResurfacingResponse(BaseModel):
    """Decision resurfacing result."""
    items: list[ResurfacedDecisionResponse]
    total_count: int
    review_due_count: int
    no_outcome_count: int


def _decision_to_response(d: ResurfacedDecision) -> ResurfacedDecisionResponse:
    return ResurfacedDecisionResponse(
        node_id=str(d.node_id),
        title=d.title,
        content=d.content,
        context=d.context,
        review_at=str(d.review_at) if d.review_at else None,
        created_at=d.created_at.isoformat(),
        resurfacing_reason=d.resurfacing_reason,
        days_since_creation=d.days_since_creation,
        has_outcome_edges=d.has_outcome_edges,
        explanation=DerivedExplanationResponse(
            summary=d.explanation.summary,
            factors=[
                {"signal": f.signal, "value": f.value, "weight": f.weight}
                for f in d.explanation.factors
            ],
            confidence=d.explanation.confidence,
            generated_at=d.explanation.generated_at.isoformat() if d.explanation.generated_at else None,
            version=d.explanation.version,
        ),
        tags=d.tags,
    )


@router.get("/resurfacing", response_model=DecisionResurfacingResponse)
async def get_decision_resurfacing(
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Section 5.7: Decision resurfacing workflow.
    Runs as query at load time, not a separate scheduler.

    Returns decisions needing outcome evaluation:
    - Decisions with review_at due (user-set override)
    - Decisions with no outcome after 7d/30d/90d

    Layer: Behavioral (queries at load time)
    Invariant D-01: All items include DerivedExplanation.
    """
    result = await get_decisions_for_resurfacing(db, user.id, limit=limit)

    return DecisionResurfacingResponse(
        items=[_decision_to_response(d) for d in result.items],
        total_count=result.total_count,
        review_due_count=result.review_due_count,
        no_outcome_count=result.no_outcome_count,
    )
