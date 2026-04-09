"""Investment holdings and transaction endpoints for the finance domain.

F2.1: CRUD for investment holdings (snapshot-based) and investment transactions
with corporate action support (split, merger, spinoff).
Ref: Finance Design Rev 3 Sections 3.3–3.4.
"""

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.enums import InvestmentTransactionType
from server.app.core.models.user import User
from server.app.domains.finance.schemas.investments import (
    InvestmentHoldingCreate,
    InvestmentHoldingListResponse,
    InvestmentHoldingResponse,
    InvestmentHoldingUpdate,
    InvestmentTransactionCreate,
    InvestmentTransactionListResponse,
    InvestmentTransactionResponse,
    InvestmentTransactionUpdate,
)
from server.app.domains.finance.services.investments import (
    create_holding,
    create_investment_transaction,
    delete_holding,
    delete_investment_transaction,
    get_holding,
    get_investment_transaction,
    list_holdings,
    list_investment_transactions,
    update_holding,
    update_investment_transaction,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------


@router.post(
    "/investments/holdings",
    response_model=InvestmentHoldingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_holding_endpoint(
    body: InvestmentHoldingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an investment holding snapshot."""
    try:
        holding = await create_holding(
            db, user.id,
            account_id=body.account_id,
            symbol=body.symbol,
            asset_type=body.asset_type,
            quantity=body.quantity,
            currency=body.currency,
            as_of_date=body.as_of_date,
            valuation_source=body.valuation_source,
            asset_name=body.asset_name,
            cost_basis=body.cost_basis,
            source=body.source,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return InvestmentHoldingResponse.model_validate(holding)


@router.get("/investments/holdings", response_model=InvestmentHoldingListResponse)
async def list_holdings_endpoint(
    account_id: uuid.UUID | None = Query(default=None),
    symbol: str | None = Query(default=None),
    as_of_date: date | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List investment holdings with optional filters."""
    items, total = await list_holdings(
        db, user.id,
        account_id=account_id, symbol=symbol, as_of_date=as_of_date,
        limit=limit, offset=offset,
    )
    return InvestmentHoldingListResponse(
        items=[InvestmentHoldingResponse.model_validate(h) for h in items],
        total=total,
    )


@router.get("/investments/holdings/{holding_id}", response_model=InvestmentHoldingResponse)
async def get_holding_endpoint(
    holding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single investment holding by ID."""
    holding = await get_holding(db, user.id, holding_id)
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    return InvestmentHoldingResponse.model_validate(holding)


@router.put("/investments/holdings/{holding_id}", response_model=InvestmentHoldingResponse)
async def update_holding_endpoint(
    holding_id: uuid.UUID,
    body: InvestmentHoldingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an investment holding snapshot."""
    holding = await update_holding(
        db, user.id, holding_id,
        symbol=body.symbol,
        asset_name=body.asset_name if body.asset_name is not None else ...,
        asset_type=body.asset_type,
        quantity=body.quantity,
        cost_basis=body.cost_basis if body.cost_basis is not None else ...,
        currency=body.currency,
        as_of_date=body.as_of_date,
        source=body.source,
        valuation_source=body.valuation_source,
    )
    if holding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")
    return InvestmentHoldingResponse.model_validate(holding)


@router.delete("/investments/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding_endpoint(
    holding_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an investment holding snapshot."""
    if not await delete_holding(db, user.id, holding_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")


# ---------------------------------------------------------------------------
# Investment Transactions
# ---------------------------------------------------------------------------


@router.post(
    "/investments/transactions",
    response_model=InvestmentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investment_transaction_endpoint(
    body: InvestmentTransactionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an investment transaction.

    Split transactions automatically adjust existing holdings' quantity
    and price_per_unit for cost basis integrity.
    """
    try:
        tx = await create_investment_transaction(
            db, user.id,
            account_id=body.account_id,
            symbol=body.symbol,
            transaction_type=body.transaction_type,
            quantity=body.quantity,
            price_per_unit=body.price_per_unit,
            total_amount=body.total_amount,
            currency=body.currency,
            occurred_at=body.occurred_at,
            lot_id=body.lot_id,
            source=body.source,
            external_id=body.external_id,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return InvestmentTransactionResponse.model_validate(tx)


@router.get("/investments/transactions", response_model=InvestmentTransactionListResponse)
async def list_investment_transactions_endpoint(
    account_id: uuid.UUID | None = Query(default=None),
    symbol: str | None = Query(default=None),
    transaction_type: InvestmentTransactionType | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List investment transactions with optional filters."""
    items, total = await list_investment_transactions(
        db, user.id,
        account_id=account_id, symbol=symbol,
        transaction_type=transaction_type,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )
    return InvestmentTransactionListResponse(
        items=[InvestmentTransactionResponse.model_validate(tx) for tx in items],
        total=total,
    )


@router.get(
    "/investments/transactions/{tx_id}",
    response_model=InvestmentTransactionResponse,
)
async def get_investment_transaction_endpoint(
    tx_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single investment transaction by ID."""
    tx = await get_investment_transaction(db, user.id, tx_id)
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment transaction not found",
        )
    return InvestmentTransactionResponse.model_validate(tx)


@router.put(
    "/investments/transactions/{tx_id}",
    response_model=InvestmentTransactionResponse,
)
async def update_investment_transaction_endpoint(
    tx_id: uuid.UUID,
    body: InvestmentTransactionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an investment transaction."""
    tx = await update_investment_transaction(
        db, user.id, tx_id,
        symbol=body.symbol,
        transaction_type=body.transaction_type,
        quantity=body.quantity,
        price_per_unit=body.price_per_unit,
        total_amount=body.total_amount,
        currency=body.currency,
        occurred_at=body.occurred_at,
        lot_id=body.lot_id if body.lot_id is not None else ...,
        source=body.source,
        notes=body.notes if body.notes is not None else ...,
    )
    if tx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment transaction not found",
        )
    return InvestmentTransactionResponse.model_validate(tx)


@router.delete(
    "/investments/transactions/{tx_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_investment_transaction_endpoint(
    tx_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an investment transaction."""
    if not await delete_investment_transaction(db, user.id, tx_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investment transaction not found",
        )
