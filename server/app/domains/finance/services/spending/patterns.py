"""
Spending pattern metrics (Section 4.3, Rev3 additions).

Three standalone Derived metrics that also feed the Alerts Engine in F3:
- Merchant concentration (30% threshold, fuzzy match pre-F3)
- Spend creep (consecutive rolling 3-month windows, ≥10% increase)
- Leakage candidates (frequency heuristic pre-F3)

Invariants:
- F-07: only expense/fee types considered.
- D-01: DerivedExplanation on every output.
- D-02: recomputable from Core + Temporal.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import FinancialTransaction
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
    start_of_month,
)
from server.app.domains.finance.services.spending._helpers import (
    POSTED_STATUSES,
    SPENDING_TYPES,
    _category_label,
    _load_category_map,
    _normalize_counterparty,
)


MERCHANT_CONCENTRATION_THRESHOLD = 0.30  # 30%
SPEND_CREEP_MIN_DELTA = 0.10  # 10% growth between consecutive windows
LEAKAGE_MIN_OCCURRENCES = 3
LEAKAGE_MAX_AVG_AMOUNT = Decimal("50.00")


async def compute_merchant_concentration(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
    threshold: float = MERCHANT_CONCENTRATION_THRESHOLD,
) -> dict:
    """
    Section 4.3: Merchant concentration — share of category spend held by a
    single counterparty. Pre-F3 fallback: fuzzy match on raw counterparty.
    """
    start_dt = datetime_at_start_of_day(period_start)
    end_dt = datetime_at_end_of_day(period_end)

    stmt = (
        select(
            FinancialTransaction.category_id,
            FinancialTransaction.counterparty,
            func.sum(func.abs(FinancialTransaction.signed_amount)),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
            FinancialTransaction.counterparty.isnot(None),
        )
        .group_by(
            FinancialTransaction.category_id,
            FinancialTransaction.counterparty,
        )
    )
    rows = (await db.execute(stmt)).all()
    cat_map = await _load_category_map(db, user_id)

    # Pre-F3: fuzzy merge by normalized counterparty key within category.
    merged: dict[tuple[uuid.UUID | None, str], dict] = {}
    for cat_id, raw_cp, total in rows:
        key = _normalize_counterparty(raw_cp)
        if key is None:
            continue
        merged_key = (cat_id, key)
        bucket = merged.setdefault(
            merged_key,
            {
                "counterparty": raw_cp or key,
                "category_id": cat_id,
                "merchant_spend": Decimal("0"),
            },
        )
        bucket["merchant_spend"] += Decimal(str(total))

    cat_totals: dict[uuid.UUID | None, Decimal] = {}
    for (cat_id, _), bucket in merged.items():
        cat_totals[cat_id] = cat_totals.get(cat_id, Decimal("0")) + bucket["merchant_spend"]

    concentrated: list[dict] = []
    for (cat_id, _), bucket in merged.items():
        category_total = cat_totals.get(cat_id, Decimal("0"))
        if category_total <= 0:
            continue
        share = float(bucket["merchant_spend"] / category_total)
        if share >= threshold:
            concentrated.append({
                "counterparty": bucket["counterparty"],
                "category_id": cat_id,
                "category_name": _category_label(cat_id, cat_map),
                "merchant_spend": bucket["merchant_spend"],
                "category_total": category_total,
                "share": share,
            })

    concentrated.sort(key=lambda e: e["share"], reverse=True)

    explanation = DerivedExplanation(
        summary=(
            f"Merchant concentration {period_start}→{period_end}: "
            f"{len(concentrated)} merchant-category pairs ≥ {threshold:.0%} "
            f"of category spend."
        ),
        factors=[
            DerivedFactor(signal="threshold", value=threshold, weight=1.0),
            DerivedFactor(
                signal="match_strategy",
                value="F3-deferred: fuzzy key on raw counterparty",
                weight=0.7,
            ),
            DerivedFactor(
                signal="flagged_count", value=len(concentrated), weight=1.0
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "threshold": threshold,
        "concentrated_merchants": concentrated,
        "explanation": explanation,
    }


async def _category_spend_window(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> dict[uuid.UUID | None, Decimal]:
    stmt = (
        select(
            FinancialTransaction.category_id,
            func.sum(func.abs(FinancialTransaction.signed_amount)),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= datetime_at_start_of_day(start),
            FinancialTransaction.occurred_at <= datetime_at_end_of_day(end),
        )
        .group_by(FinancialTransaction.category_id)
    )
    rows = (await db.execute(stmt)).all()
    return {row[0]: Decimal(str(row[1])) for row in rows}


async def compute_spend_creep(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
    min_delta_pct: float = SPEND_CREEP_MIN_DELTA,
) -> dict:
    """
    Section 4.3: Spend creep — sustained increase detected by comparing
    consecutive 3-month rolling averages.
    """
    if as_of_date is None:
        as_of_date = date.today()

    later_end = start_of_month(as_of_date) - timedelta(days=1)
    ref = start_of_month(later_end)
    for _ in range(2):
        ref = start_of_month(ref - timedelta(days=1))
    later_start = ref

    earlier_end = later_start - timedelta(days=1)
    ref2 = start_of_month(earlier_end)
    for _ in range(2):
        ref2 = start_of_month(ref2 - timedelta(days=1))
    earlier_start = ref2

    later_totals = await _category_spend_window(
        db, user_id, later_start, later_end
    )
    earlier_totals = await _category_spend_window(
        db, user_id, earlier_start, earlier_end
    )
    cat_map = await _load_category_map(db, user_id)

    creeping: list[dict] = []
    for cat_id, later_total in later_totals.items():
        earlier_total = earlier_totals.get(cat_id, Decimal("0"))
        earlier_avg = earlier_total / Decimal("3") if earlier_total else Decimal("0")
        later_avg = later_total / Decimal("3")
        if earlier_avg <= 0:
            continue
        delta_pct = float((later_avg - earlier_avg) / earlier_avg)
        if delta_pct >= min_delta_pct:
            creeping.append({
                "category_id": cat_id,
                "category_name": _category_label(cat_id, cat_map),
                "earlier_window_avg": earlier_avg,
                "later_window_avg": later_avg,
                "delta_pct": delta_pct,
                "window_months": 3,
            })

    creeping.sort(key=lambda e: e["delta_pct"], reverse=True)

    explanation = DerivedExplanation(
        summary=(
            f"Spend creep as of {as_of_date}: {len(creeping)} categories "
            f"up ≥ {min_delta_pct:.0%} vs prior 3-month average."
        ),
        factors=[
            DerivedFactor(
                signal="min_delta_pct", value=min_delta_pct, weight=1.0
            ),
            DerivedFactor(
                signal="earlier_window",
                value=f"{earlier_start}→{earlier_end}",
                weight=1.0,
            ),
            DerivedFactor(
                signal="later_window",
                value=f"{later_start}→{later_end}",
                weight=1.0,
            ),
            DerivedFactor(
                signal="creeping_count", value=len(creeping), weight=1.0
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "as_of_date": as_of_date,
        "creeping_categories": creeping,
        "explanation": explanation,
    }


async def compute_leakage_candidates(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
    min_occurrences: int = LEAKAGE_MIN_OCCURRENCES,
    max_avg_amount: Decimal = LEAKAGE_MAX_AVG_AMOUNT,
) -> dict:
    """
    Section 4.3: Leakage candidates — low-value repeated discretionary spend.
    Pre-F3 frequency heuristic: a counterparty that appears ≥ N times with
    average amount ≤ threshold.
    """
    start_dt = datetime_at_start_of_day(period_start)
    end_dt = datetime_at_end_of_day(period_end)

    stmt = (
        select(FinancialTransaction)
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
            FinancialTransaction.counterparty.isnot(None),
        )
    )
    txs = (await db.execute(stmt)).scalars().all()

    cat_map = await _load_category_map(db, user_id)
    grouped: dict[str, dict] = {}
    for tx in txs:
        key = _normalize_counterparty(tx.counterparty)
        if key is None:
            continue
        bucket = grouped.setdefault(
            key,
            {
                "counterparty": tx.counterparty,
                "category_id": tx.category_id,
                "category_name": _category_label(tx.category_id, cat_map),
                "total_spend": Decimal("0"),
                "occurrence_count": 0,
                "first_seen": tx.occurred_at,
                "last_seen": tx.occurred_at,
            },
        )
        bucket["total_spend"] += abs(Decimal(str(tx.signed_amount)))
        bucket["occurrence_count"] += 1
        if tx.occurred_at < bucket["first_seen"]:
            bucket["first_seen"] = tx.occurred_at
        if tx.occurred_at > bucket["last_seen"]:
            bucket["last_seen"] = tx.occurred_at

    candidates: list[dict] = []
    for _, bucket in grouped.items():
        count = bucket["occurrence_count"]
        if count < min_occurrences:
            continue
        avg_amount = bucket["total_spend"] / Decimal(count)
        if avg_amount > max_avg_amount:
            continue
        candidates.append({
            "counterparty": bucket["counterparty"],
            "category_id": bucket["category_id"],
            "category_name": bucket["category_name"],
            "total_spend": bucket["total_spend"],
            "occurrence_count": count,
            "avg_amount": avg_amount,
            "first_seen": bucket["first_seen"].isoformat(),
            "last_seen": bucket["last_seen"].isoformat(),
        })

    candidates.sort(key=lambda c: c["occurrence_count"], reverse=True)

    explanation = DerivedExplanation(
        summary=(
            f"Leakage candidates {period_start}→{period_end}: "
            f"{len(candidates)} repeated low-value counterparties. "
            f"Frequency heuristic pre-F3."
        ),
        factors=[
            DerivedFactor(
                signal="min_occurrences", value=min_occurrences, weight=1.0
            ),
            DerivedFactor(
                signal="max_avg_amount",
                value=str(max_avg_amount),
                weight=1.0,
            ),
            DerivedFactor(
                signal="candidate_count", value=len(candidates), weight=1.0
            ),
            DerivedFactor(
                signal="strategy",
                value="F3-deferred: recurring_patterns will supersede",
                weight=0.6,
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "candidates": candidates,
        "explanation": explanation,
    }
