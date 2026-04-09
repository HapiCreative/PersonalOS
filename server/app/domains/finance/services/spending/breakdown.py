"""
Category breakdown with hierarchy rollup (Section 4.3).

Invariant D-01: DerivedExplanation required.
Invariant D-02: recomputable from Core + Temporal.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import FinancialTransaction
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
)
from server.app.domains.finance.services.spending._helpers import (
    POSTED_STATUSES,
    SPENDING_TYPES,
    _category_label,
    _load_category_map,
    _rollup_to_parent,
)


async def compute_category_breakdown(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> dict:
    """Section 4.3: Category breakdown with hierarchy rollup."""
    start_dt = datetime_at_start_of_day(period_start)
    end_dt = datetime_at_end_of_day(period_end)

    stmt = (
        select(
            FinancialTransaction.category_id,
            func.coalesce(
                func.sum(func.abs(FinancialTransaction.signed_amount)),
                Decimal("0"),
            ),
            func.count(),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
        .group_by(FinancialTransaction.category_id)
    )
    rows = (await db.execute(stmt)).all()

    cat_map = await _load_category_map(db, user_id)
    spend_leaf: dict[uuid.UUID | None, Decimal] = {}
    counts: dict[uuid.UUID | None, int] = {}
    for cat_id, total, count in rows:
        spend_leaf[cat_id] = Decimal(str(total))
        counts[cat_id] = int(count)

    spend_rolled = _rollup_to_parent(spend_leaf, cat_map)
    total_spend = sum(spend_leaf.values(), start=Decimal("0"))

    categories: list[dict] = []
    for cat_id, amount in sorted(
        spend_rolled.items(), key=lambda kv: kv[1], reverse=True
    ):
        is_rollup = cat_id in spend_rolled and cat_id not in spend_leaf
        parent_id = None
        if cat_id is not None and cat_id in cat_map:
            parent_id = cat_map[cat_id].parent_id
        pct = 0.0
        if total_spend > 0:
            pct = float(amount / total_spend)
        categories.append({
            "category_id": cat_id,
            "category_name": _category_label(cat_id, cat_map),
            "parent_category_id": parent_id,
            "total_spend": amount,
            "transaction_count": counts.get(cat_id, 0),
            "pct_of_total": pct,
            "is_rollup": is_rollup,
        })

    explanation = DerivedExplanation(
        summary=(
            f"Spending by category {period_start}→{period_end}: "
            f"{total_spend} total across {len(spend_leaf)} leaf categories "
            f"(hierarchy rollup applied to parents)."
        ),
        factors=[
            DerivedFactor(
                signal="total_spend", value=str(total_spend), weight=1.0
            ),
            DerivedFactor(
                signal="leaf_category_count",
                value=len(spend_leaf),
                weight=1.0,
            ),
            DerivedFactor(
                signal="transaction_count",
                value=sum(counts.values()),
                weight=1.0,
            ),
            DerivedFactor(
                signal="rollup_policy",
                value="child → parent hierarchy",
                weight=1.0,
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "total_spend": total_spend,
        "categories": categories,
        "explanation": explanation,
    }
