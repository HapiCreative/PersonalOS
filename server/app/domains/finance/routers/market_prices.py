"""Market price cache endpoints for the finance domain.

F2.1: Manual entry for MVP; API fetch post-MVP.
Derived cache — purgeable at any time.
Ref: Finance Design Rev 3 Section 4.6.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.market_prices import (
    MarketPriceCreate,
    MarketPriceListResponse,
    MarketPriceResponse,
)
from server.app.domains.finance.services.market_prices import (
    delete_market_price,
    get_market_price,
    list_market_prices,
    upsert_market_price,
)

router = APIRouter()


@router.post(
    "/market-prices",
    response_model=MarketPriceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_market_price_endpoint(
    body: MarketPriceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a market price entry (manual for MVP)."""
    mp = await upsert_market_price(
        db,
        symbol=body.symbol,
        price=body.price,
        currency=body.currency,
        price_date=body.price_date,
        source=body.source,
    )
    return MarketPriceResponse.model_validate(mp)


@router.get("/market-prices", response_model=MarketPriceListResponse)
async def list_market_prices_endpoint(
    symbol: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List market prices with optional filters."""
    items, total = await list_market_prices(
        db,
        symbol=symbol, date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return MarketPriceListResponse(
        items=[MarketPriceResponse.model_validate(mp) for mp in items],
        total=total,
    )


@router.get("/market-prices/lookup", response_model=MarketPriceResponse)
async def lookup_market_price_endpoint(
    symbol: str = Query(min_length=1),
    price_date: date | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Look up a market price by symbol (optionally on a specific date)."""
    mp = await get_market_price(db, symbol, price_date)
    if mp is None:
        detail = f"No price found for {symbol}"
        if price_date:
            detail += f" on {price_date}"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return MarketPriceResponse.model_validate(mp)


@router.delete("/market-prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market_price_endpoint(
    price_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a market price entry."""
    if not await delete_market_price(db, price_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Market price not found",
        )
