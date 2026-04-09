"""Exchange rate service functions.

F2.1: Historical currency exchange rates per pair per date.
Invariant F-10: historical net worth always uses rate from snapshot date, never current.
Ref: Finance Design Rev 3 Section 3.5.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.models.investments import ExchangeRate


async def upsert_exchange_rate(
    db: AsyncSession,
    *,
    base_currency: str,
    quote_currency: str,
    rate: Decimal,
    rate_date: date,
    source: str,
) -> ExchangeRate:
    """Create or update an exchange rate for a currency pair on a given date.

    Upserts on (base_currency, quote_currency, rate_date) uniqueness.
    Invariant F-10: rates stored per date for historical lookups.
    """
    stmt = select(ExchangeRate).where(
        ExchangeRate.base_currency == base_currency,
        ExchangeRate.quote_currency == quote_currency,
        ExchangeRate.rate_date == rate_date,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.rate = rate
        existing.source = source
        await db.flush()
        return existing

    er = ExchangeRate(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate=rate,
        rate_date=rate_date,
        source=source,
    )
    db.add(er)
    await db.flush()
    return er


async def get_exchange_rate(
    db: AsyncSession,
    base_currency: str,
    quote_currency: str,
    rate_date: date,
) -> ExchangeRate | None:
    """Look up a rate for a specific currency pair and date.

    Invariant F-10: always use the rate from the snapshot date.
    """
    stmt = select(ExchangeRate).where(
        ExchangeRate.base_currency == base_currency,
        ExchangeRate.quote_currency == quote_currency,
        ExchangeRate.rate_date == rate_date,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_closest_exchange_rate(
    db: AsyncSession,
    base_currency: str,
    quote_currency: str,
    target_date: date,
) -> ExchangeRate | None:
    """Look up the closest rate on or before target_date.

    Useful when an exact-date rate is unavailable (e.g. weekends).
    """
    stmt = (
        select(ExchangeRate)
        .where(
            ExchangeRate.base_currency == base_currency,
            ExchangeRate.quote_currency == quote_currency,
            ExchangeRate.rate_date <= target_date,
        )
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_exchange_rates(
    db: AsyncSession,
    *,
    base_currency: str | None = None,
    quote_currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExchangeRate], int]:
    """List exchange rates with optional filters."""
    filters: list = []
    if base_currency is not None:
        filters.append(ExchangeRate.base_currency == base_currency)
    if quote_currency is not None:
        filters.append(ExchangeRate.quote_currency == quote_currency)
    if date_from is not None:
        filters.append(ExchangeRate.rate_date >= date_from)
    if date_to is not None:
        filters.append(ExchangeRate.rate_date <= date_to)

    total = (await db.execute(
        select(func.count()).select_from(ExchangeRate).where(*filters)
        if filters else select(func.count()).select_from(ExchangeRate)
    )).scalar_one()

    stmt = select(ExchangeRate)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(ExchangeRate.rate_date.desc()).limit(limit).offset(offset)

    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def delete_exchange_rate(
    db: AsyncSession, rate_id: uuid.UUID,
) -> bool:
    """Delete an exchange rate by ID. Returns True if deleted."""
    stmt = select(ExchangeRate).where(ExchangeRate.id == rate_id)
    er = (await db.execute(stmt)).scalar_one_or_none()
    if er is None:
        return False
    await db.delete(er)
    await db.flush()
    return True
