"""
Shared helpers + constants for spending intelligence.

Ref: Finance Design Rev 3 Section 4.3. Invariant F-07 excludes
transfer/investment types — only expense/fee transactions are eligible here.
"""

import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    FinancialTransactionStatus,
    FinancialTransactionType,
)
from server.app.core.models.node import FinancialCategory


# Invariant F-07: spending-eligible types only (expenses + fees).
SPENDING_TYPES: list[FinancialTransactionType] = [
    FinancialTransactionType.EXPENSE,
    FinancialTransactionType.FEE,
]
POSTED_STATUSES: list[FinancialTransactionStatus] = [
    FinancialTransactionStatus.POSTED,
    FinancialTransactionStatus.SETTLED,
]

TREND_MULTIPLIER = Decimal("1.5")
ANOMALY_MULTIPLIER = Decimal("3.0")


async def _load_category_map(
    db: AsyncSession, user_id: uuid.UUID
) -> dict[uuid.UUID, FinancialCategory]:
    stmt = select(FinancialCategory).where(FinancialCategory.user_id == user_id)
    rows = (await db.execute(stmt)).scalars().all()
    return {c.id: c for c in rows}


def _category_label(
    category_id: uuid.UUID | None,
    cat_map: dict[uuid.UUID, FinancialCategory],
) -> str:
    if category_id is None:
        return "Uncategorized"
    cat = cat_map.get(category_id)
    return cat.name if cat is not None else "Unknown"


def _rollup_to_parent(
    spend_by_cat: dict[uuid.UUID | None, Decimal],
    cat_map: dict[uuid.UUID, FinancialCategory],
) -> dict[uuid.UUID | None, Decimal]:
    """
    Section 4.3: hierarchy rollup. Adds child spend to each ancestor so
    callers can show either leaf or parent totals.
    """
    rolled: dict[uuid.UUID | None, Decimal] = dict(spend_by_cat)
    for cat_id, amount in list(spend_by_cat.items()):
        if cat_id is None:
            continue
        current = cat_map.get(cat_id)
        while current is not None and current.parent_id is not None:
            rolled[current.parent_id] = rolled.get(
                current.parent_id, Decimal("0")
            ) + amount
            current = cat_map.get(current.parent_id)
    return rolled


def _normalize_counterparty(raw: str | None) -> str | None:
    """
    Pre-F3 fuzzy key for a counterparty string: lowercase, strip punctuation,
    collapse whitespace, drop trailing store numbers. Real counterparty
    resolution lands in F3 (counterparty_entities).
    """
    if raw is None:
        return None
    s = raw.strip().lower()
    s = re.sub(r"#\d+", "", s)
    s = re.sub(r"\s+\d{3,}$", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None
