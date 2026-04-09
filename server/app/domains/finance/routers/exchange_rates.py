"""Exchange rate endpoints for the finance domain.

F2.1: Historical currency exchange rates CRUD.
Invariant F-10: historical net worth always uses rate from snapshot date.
Ref: Finance Design Rev 3 Section 3.5.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.exchange_rates import (
    ExchangeRateCreate,
    ExchangeRateListResponse,
    ExchangeRateResponse,
)
from server.app.domains.finance.services.exchange_rates import (
    delete_exchange_rate,
    get_exchange_rate,
    list_exchange_rates,
    upsert_exchange_rate,
)

router = APIRouter()


@router.post(
    "/exchange-rates",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_exchange_rate_endpoint(
    body: ExchangeRateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update an exchange rate for a currency pair on a date."""
    er = await upsert_exchange_rate(
        db,
        base_currency=body.base_currency,
        quote_currency=body.quote_currency,
        rate=body.rate,
        rate_date=body.rate_date,
        source=body.source,
    )
    return ExchangeRateResponse.model_validate(er)


@router.get("/exchange-rates", response_model=ExchangeRateListResponse)
async def list_exchange_rates_endpoint(
    base_currency: str | None = Query(default=None, min_length=3, max_length=3),
    quote_currency: str | None = Query(default=None, min_length=3, max_length=3),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List exchange rates with optional filters."""
    items, total = await list_exchange_rates(
        db,
        base_currency=base_currency, quote_currency=quote_currency,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return ExchangeRateListResponse(
        items=[ExchangeRateResponse.model_validate(er) for er in items],
        total=total,
    )


@router.get("/exchange-rates/lookup", response_model=ExchangeRateResponse)
async def lookup_exchange_rate_endpoint(
    base_currency: str = Query(min_length=3, max_length=3),
    quote_currency: str = Query(min_length=3, max_length=3),
    rate_date: date = Query(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Look up a specific exchange rate by currency pair and date.

    Invariant F-10: Use rate from snapshot date, never current date.
    """
    er = await get_exchange_rate(db, base_currency, quote_currency, rate_date)
    if er is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rate found for {base_currency}/{quote_currency} on {rate_date}",
        )
    return ExchangeRateResponse.model_validate(er)


@router.delete("/exchange-rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exchange_rate_endpoint(
    rate_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an exchange rate entry."""
    if not await delete_exchange_rate(db, rate_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exchange rate not found",
        )
