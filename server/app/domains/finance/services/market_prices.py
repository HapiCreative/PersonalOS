"""Market price cache service functions.

F2.1: Derived cache — purgeable at any time.
Manual entry for MVP; API fetch post-MVP.
Ref: Finance Design Rev 3 Section 4.6.
"""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.domains.finance.models.investments import MarketPrice


async def upsert_market_price(
    db: AsyncSession,
    *,
    symbol: str,
    price: Decimal,
    currency: str,
    price_date: date,
    source: str,
) -> MarketPrice:
    """Create or update a market price for a symbol on a given date.

    Upserts on (symbol, price_date, source) uniqueness.
    """
    stmt = select(MarketPrice).where(
        MarketPrice.symbol == symbol,
        MarketPrice.price_date == price_date,
        MarketPrice.source == source,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.price = price
        existing.currency = currency
        await db.flush()
        return existing

    mp = MarketPrice(
        symbol=symbol,
        price=price,
        currency=currency,
        price_date=price_date,
        source=source,
    )
    db.add(mp)
    await db.flush()
    return mp


async def get_market_price(
    db: AsyncSession,
    symbol: str,
    price_date: date | None = None,
) -> MarketPrice | None:
    """Get the market price for a symbol.

    If price_date is provided, returns the exact match.
    Otherwise returns the most recent price for the symbol.
    """
    if price_date is not None:
        stmt = (
            select(MarketPrice)
            .where(MarketPrice.symbol == symbol, MarketPrice.price_date == price_date)
            .order_by(MarketPrice.fetched_at.desc())
            .limit(1)
        )
    else:
        stmt = (
            select(MarketPrice)
            .where(MarketPrice.symbol == symbol)
            .order_by(MarketPrice.price_date.desc(), MarketPrice.fetched_at.desc())
            .limit(1)
        )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_market_prices(
    db: AsyncSession,
    *,
    symbol: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MarketPrice], int]:
    """List market prices with optional filters."""
    filters: list = []
    if symbol is not None:
        filters.append(MarketPrice.symbol == symbol)
    if date_from is not None:
        filters.append(MarketPrice.price_date >= date_from)
    if date_to is not None:
        filters.append(MarketPrice.price_date <= date_to)

    count_stmt = select(func.count()).select_from(MarketPrice)
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(MarketPrice)
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(MarketPrice.price_date.desc()).limit(limit).offset(offset)

    items = list((await db.execute(stmt)).scalars().all())
    return items, total


async def delete_market_price(
    db: AsyncSession, price_id: uuid.UUID,
) -> bool:
    """Delete a market price by ID. Returns True if deleted."""
    stmt = select(MarketPrice).where(MarketPrice.id == price_id)
    mp = (await db.execute(stmt)).scalar_one_or_none()
    if mp is None:
        return False
    await db.delete(mp)
    await db.flush()
    return True
