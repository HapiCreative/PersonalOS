"""
Trend detection + anomaly detection (Section 4.3).

Trend: current-month category spend vs rolling 3-month average (1.5× flag).
Anomalies: individual transactions > 3× category median with DerivedExplanation.

Invariants:
- F-07: only expense/fee types considered.
- D-01: DerivedExplanation on every output (and per-anomaly).
- D-02: recomputable from Core + Temporal.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.node import FinancialTransaction
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    datetime_at_end_of_day,
    datetime_at_start_of_day,
    end_of_month,
    start_of_month,
)
from server.app.domains.finance.services.spending._helpers import (
    ANOMALY_MULTIPLIER,
    POSTED_STATUSES,
    SPENDING_TYPES,
    TREND_MULTIPLIER,
    _category_label,
    _load_category_map,
)


async def _category_totals(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> dict[uuid.UUID | None, Decimal]:
    stmt = (
        select(
            FinancialTransaction.category_id,
            func.coalesce(
                func.sum(func.abs(FinancialTransaction.signed_amount)),
                Decimal("0"),
            ),
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


async def compute_spending_trends(
    db: AsyncSession,
    user_id: uuid.UUID,
    as_of_date: date | None = None,
) -> dict:
    """
    Section 4.3: Trend detection — flag categories where current-month spend
    exceeds 1.5× the rolling 3-month average.
    """
    if as_of_date is None:
        as_of_date = date.today()

    current_start = start_of_month(as_of_date)
    current_end = end_of_month(as_of_date)

    # Rolling 3-month baseline: three calendar months before current month.
    baseline_end = current_start - timedelta(days=1)
    ref = start_of_month(baseline_end)
    for _ in range(2):
        ref = start_of_month(ref - timedelta(days=1))
    baseline_start = ref

    cat_map = await _load_category_map(db, user_id)
    current_totals = await _category_totals(db, user_id, current_start, current_end)
    baseline_totals = await _category_totals(db, user_id, baseline_start, baseline_end)

    trending: list[dict] = []
    for cat_id, current_spend in current_totals.items():
        baseline_total = baseline_totals.get(cat_id, Decimal("0"))
        rolling_avg = baseline_total / Decimal("3") if baseline_total else Decimal("0")
        if rolling_avg <= 0:
            continue
        ratio = float(current_spend / rolling_avg)
        if current_spend >= rolling_avg * TREND_MULTIPLIER:
            trending.append({
                "category_id": cat_id,
                "category_name": _category_label(cat_id, cat_map),
                "current_month_spend": current_spend,
                "rolling_3month_avg": rolling_avg,
                "ratio": ratio,
                "is_trending_up": True,
            })

    trending.sort(key=lambda e: e["ratio"], reverse=True)

    explanation = DerivedExplanation(
        summary=(
            f"Trend detection as of {as_of_date}: "
            f"{len(trending)} categories ≥ 1.5× 3-month rolling average."
        ),
        factors=[
            DerivedFactor(
                signal="threshold",
                value="1.5× rolling 3-month average",
                weight=1.0,
            ),
            DerivedFactor(
                signal="baseline_window",
                value=f"{baseline_start}→{baseline_end}",
                weight=1.0,
            ),
            DerivedFactor(
                signal="current_window",
                value=f"{current_start}→{current_end}",
                weight=1.0,
            ),
            DerivedFactor(
                signal="trending_count", value=len(trending), weight=1.0
            ),
        ],
        generated_at=datetime.now(timezone.utc),
        version="f2c-1",
    )
    DerivedExplanation.validate(explanation)

    return {
        "as_of_date": as_of_date,
        "trending_categories": trending,
        "explanation": explanation,
    }


async def compute_spending_anomalies(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
    lookback_days: int = 180,
) -> dict:
    """
    Section 4.3: Anomaly detection — transactions > 3× category median.
    Each anomaly gets its own DerivedExplanation (D-01).
    """
    cat_map = await _load_category_map(db, user_id)
    start_dt = datetime_at_start_of_day(period_start)
    end_dt = datetime_at_end_of_day(period_end)
    baseline_start_dt = datetime_at_start_of_day(
        period_start - timedelta(days=lookback_days)
    )

    baseline_stmt = (
        select(
            FinancialTransaction.category_id,
            func.abs(FinancialTransaction.signed_amount),
        )
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= baseline_start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    baseline_rows = (await db.execute(baseline_stmt)).all()
    by_cat: dict[uuid.UUID | None, list[Decimal]] = {}
    for cat_id, amt in baseline_rows:
        by_cat.setdefault(cat_id, []).append(Decimal(str(amt)))
    medians: dict[uuid.UUID | None, Decimal] = {
        cat_id: Decimal(str(median(vals)))
        for cat_id, vals in by_cat.items()
        if vals
    }

    tx_stmt = (
        select(FinancialTransaction)
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.is_voided.is_(False),
            FinancialTransaction.transaction_type.in_(SPENDING_TYPES),
            FinancialTransaction.status.in_(POSTED_STATUSES),
            FinancialTransaction.occurred_at >= start_dt,
            FinancialTransaction.occurred_at <= end_dt,
        )
    )
    target_txs = (await db.execute(tx_stmt)).scalars().all()

    anomalies: list[dict] = []
    for tx in target_txs:
        amt = abs(Decimal(str(tx.signed_amount)))
        median_amt = medians.get(tx.category_id)
        if median_amt is None or median_amt == 0:
            continue
        ratio = amt / median_amt
        if ratio >= ANOMALY_MULTIPLIER:
            category_name = _category_label(tx.category_id, cat_map)
            explanation = DerivedExplanation(
                summary=(
                    f"Transaction {amt} {tx.currency} in '{category_name}' "
                    f"is {float(ratio):.1f}× the category median ({median_amt})."
                ),
                factors=[
                    DerivedFactor(signal="amount", value=str(amt), weight=1.0),
                    DerivedFactor(
                        signal="category_median",
                        value=str(median_amt),
                        weight=1.0,
                    ),
                    DerivedFactor(signal="ratio", value=float(ratio), weight=1.0),
                    DerivedFactor(
                        signal="lookback_days",
                        value=lookback_days,
                        weight=0.6,
                    ),
                ],
                generated_at=datetime.now(timezone.utc),
                version="f2c-1",
            )
            DerivedExplanation.validate(explanation)
            anomalies.append({
                "transaction_id": tx.id,
                "account_id": tx.account_id,
                "category_id": tx.category_id,
                "category_name": category_name,
                "amount": amt,
                "currency": tx.currency,
                "occurred_at": tx.occurred_at.isoformat(),
                "category_median": median_amt,
                "ratio": float(ratio),
                "counterparty": tx.counterparty,
                "explanation": explanation,
            })

    anomalies.sort(key=lambda a: a["ratio"], reverse=True)

    return {
        "period_start": period_start,
        "period_end": period_end,
        "anomalies": anomalies,
    }
