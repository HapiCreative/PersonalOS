"""
Decision resurfacing behavioral service (Section 5.7).

Behavioral workflow that resurfaces past decisions for outcome evaluation.
- Decisions with review_at due (user-set override)
- Decisions with no outcome after: 7 days (short-term), 30 days (medium), 90 days (long-term)
- Runs as query at load time, not a separate scheduler.

Section 8.1: behavioral/ — decision_resurfacing
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import Node, MemoryNode
from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    NodeType, MemoryType, EdgeRelationType, EdgeState,
)
from server.app.derived.schemas import DerivedExplanation, DerivedFactor


# Resurfacing thresholds for decisions without outcomes (Section 5.7)
DECISION_THRESHOLDS = {
    "short_term": timedelta(days=7),
    "medium_term": timedelta(days=30),
    "long_term": timedelta(days=90),
}


@dataclass
class ResurfacedDecision:
    """A decision that should be resurfaced for evaluation."""
    node_id: uuid.UUID
    title: str
    content: str
    context: str | None
    review_at: date | None
    created_at: datetime
    resurfacing_reason: str  # "review_due", "no_outcome_7d", "no_outcome_30d", "no_outcome_90d"
    days_since_creation: int
    has_outcome_edges: bool
    explanation: DerivedExplanation
    tags: list[str] = field(default_factory=list)


@dataclass
class DecisionResurfacingResult:
    """Result of decision resurfacing query."""
    items: list[ResurfacedDecision]
    total_count: int
    review_due_count: int
    no_outcome_count: int


async def _check_has_outcome_edges(
    db: AsyncSession,
    node_id: uuid.UUID,
) -> bool:
    """
    Check if a decision memory has any outgoing edges that indicate
    an outcome was recorded (e.g., journal_reflects_on pointing to the decision,
    or semantic_reference from the decision to another node).
    """
    # Check for any active edges connecting this decision to other nodes
    # that would indicate follow-up / outcome
    stmt = (
        select(func.count())
        .select_from(Edge)
        .where(
            or_(
                Edge.source_id == node_id,
                Edge.target_id == node_id,
            ),
            Edge.state == EdgeState.ACTIVE,
            # Exclude provenance edges (those are about creation, not outcome)
            Edge.relation_type.notin_([
                EdgeRelationType.DERIVED_FROM_SOURCE,
                EdgeRelationType.CAPTURED_FOR,
            ]),
        )
    )
    result = await db.execute(stmt)
    count = result.scalar_one()
    return count > 0


async def get_decisions_for_resurfacing(
    db: AsyncSession,
    owner_id: uuid.UUID,
    limit: int = 10,
) -> DecisionResurfacingResult:
    """
    Section 5.7: Decision resurfacing workflow.
    Runs as query at load time, not scheduler.

    Returns decisions that need evaluation:
    1. Decisions with review_at <= today (user-set override)
    2. Decisions with no outcome after 7d/30d/90d
    """
    now = datetime.now(timezone.utc)
    today = date.today()

    # Fetch all non-archived decision memories for the user
    stmt = (
        select(Node, MemoryNode)
        .join(MemoryNode, MemoryNode.node_id == Node.id)
        .where(
            Node.owner_id == owner_id,
            Node.type == NodeType.MEMORY,
            Node.archived_at.is_(None),
            MemoryNode.memory_type == MemoryType.DECISION,
        )
        .order_by(Node.created_at.desc())
    )
    result = await db.execute(stmt)
    all_decisions = list(result.all())

    resurfaced: list[ResurfacedDecision] = []
    review_due_count = 0
    no_outcome_count = 0

    for node, memory in all_decisions:
        days_since = (now - node.created_at.replace(tzinfo=timezone.utc)).days
        has_outcomes = await _check_has_outcome_edges(db, node.id)

        reason: str | None = None
        factors: list[DerivedFactor] = []

        # Priority 1: User-set review_at is due
        if memory.review_at is not None:
            review_date = memory.review_at
            if isinstance(review_date, datetime):
                review_date = review_date.date()
            if review_date <= today:
                reason = "review_due"
                factors.append(DerivedFactor(
                    signal="review_at",
                    value=str(review_date),
                    weight=1.0,
                ))
                review_due_count += 1

        # Priority 2: No outcome edges and past threshold
        if reason is None and not has_outcomes:
            if days_since >= DECISION_THRESHOLDS["long_term"].days:
                reason = "no_outcome_90d"
                factors.append(DerivedFactor(
                    signal="days_without_outcome",
                    value=days_since,
                    weight=0.9,
                ))
                no_outcome_count += 1
            elif days_since >= DECISION_THRESHOLDS["medium_term"].days:
                reason = "no_outcome_30d"
                factors.append(DerivedFactor(
                    signal="days_without_outcome",
                    value=days_since,
                    weight=0.7,
                ))
                no_outcome_count += 1
            elif days_since >= DECISION_THRESHOLDS["short_term"].days:
                reason = "no_outcome_7d"
                factors.append(DerivedFactor(
                    signal="days_without_outcome",
                    value=days_since,
                    weight=0.5,
                ))
                no_outcome_count += 1

        if reason is None:
            continue

        # Build DerivedExplanation (Invariant D-01)
        summary_map = {
            "review_due": f"Review was scheduled for {memory.review_at}",
            "no_outcome_7d": f"Decision made {days_since} days ago with no recorded outcome",
            "no_outcome_30d": f"Decision made {days_since} days ago — consider evaluating results",
            "no_outcome_90d": f"Decision made {days_since} days ago — long overdue for outcome review",
        }
        factors.append(DerivedFactor(
            signal="has_outcome_edges",
            value=has_outcomes,
            weight=0.3,
        ))

        explanation = DerivedExplanation(
            summary=summary_map.get(reason, "Decision needs review"),
            factors=factors,
            generated_at=now,
            version="pb-1.0",
        )

        resurfaced.append(ResurfacedDecision(
            node_id=node.id,
            title=node.title,
            content=memory.content,
            context=memory.context,
            review_at=memory.review_at.date() if isinstance(memory.review_at, datetime) else memory.review_at,
            created_at=node.created_at,
            resurfacing_reason=reason,
            days_since_creation=days_since,
            has_outcome_edges=has_outcomes,
            explanation=explanation,
            tags=memory.tags or [],
        ))

    # Sort: review_due first, then by days_since_creation descending
    reason_priority = {"review_due": 0, "no_outcome_90d": 1, "no_outcome_30d": 2, "no_outcome_7d": 3}
    resurfaced.sort(key=lambda d: (reason_priority.get(d.resurfacing_reason, 99), -d.days_since_creation))

    # Apply limit
    resurfaced = resurfaced[:limit]

    return DecisionResurfacingResult(
        items=resurfaced,
        total_count=len(resurfaced),
        review_due_count=review_due_count,
        no_outcome_count=no_outcome_count,
    )
