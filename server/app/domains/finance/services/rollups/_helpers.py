"""
Internal helpers shared across rollup sub-modules. Not part of the public
rollup API — always import via the sub-module that owns the caller.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.services.spending import (
    compute_category_breakdown,
)


async def top_expense_categories(
    db: AsyncSession,
    user_id: uuid.UUID,
    start: date,
    end: date,
    limit: int = 5,
) -> list[dict]:
    """Top N leaf categories by spend for the weekly/monthly rollup JSONB."""
    breakdown = await compute_category_breakdown(db, user_id, start, end)
    top = breakdown["categories"][:limit]
    return [
        {
            "category_id": str(c["category_id"]) if c["category_id"] else None,
            "category_name": c["category_name"],
            "total_spend": str(c["total_spend"]),
            "pct_of_total": c["pct_of_total"],
        }
        for c in top
    ]


async def variance_flags_vs_prior_4_weeks(
    db: AsyncSession,
    user_id: uuid.UUID,
    current_start: date,
    current_end: date,
    threshold: float = 0.5,
) -> list[dict]:
    """
    Category variance flags. Compares current window's per-category spend to
    the per-week average across the prior 4 weeks. Flags ≥ threshold increase.
    """
    current = await compute_category_breakdown(
        db, user_id, current_start, current_end
    )
    current_map: dict = {
        c["category_id"]: c["total_spend"] for c in current["categories"]
        if not c["is_rollup"]
    }

    baseline_start = current_start - timedelta(days=28)
    baseline_end = current_start - timedelta(days=1)
    baseline = await compute_category_breakdown(
        db, user_id, baseline_start, baseline_end
    )
    baseline_map: dict = {
        c["category_id"]: c["total_spend"] for c in baseline["categories"]
        if not c["is_rollup"]
    }

    flags: list[dict] = []
    for cat_id, cur_total in current_map.items():
        base_total = baseline_map.get(cat_id, Decimal("0"))
        base_avg = base_total / Decimal("4") if base_total else Decimal("0")
        if base_avg <= 0:
            continue
        delta = float((cur_total - base_avg) / base_avg)
        if delta >= threshold:
            flags.append({
                "category_id": str(cat_id) if cat_id else None,
                "current_window_spend": str(cur_total),
                "baseline_weekly_avg": str(base_avg),
                "delta_pct": delta,
            })
    return flags
