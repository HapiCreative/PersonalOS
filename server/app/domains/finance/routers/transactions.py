"""Transaction CRUD, audit trail, and smart defaults endpoints for the finance domain."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.enums import FinancialTransactionStatus
from server.app.core.models.user import User
from server.app.domains.finance.schemas.transactions import (
    ManualEntryDefaults,
    TransactionCreate,
    TransactionHistoryListResponse,
    TransactionHistoryResponse,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from server.app.domains.finance.services.transactions import (
    create_transaction,
    get_manual_entry_defaults,
    get_transaction,
    get_transaction_history,
    list_transactions,
    update_transaction,
    void_transaction,
)

router = APIRouter()


@router.post("/transactions", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction_endpoint(
    body: TransactionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a financial transaction.
    Invariant F-02: amount must be positive.
    Invariant F-11: creates audit history row.
    """
    try:
        tx = await create_transaction(
            db, user.id,
            account_id=body.account_id,
            transaction_type=body.transaction_type,
            amount=body.amount,
            currency=body.currency,
            status=body.status,
            category_id=body.category_id,
            subcategory_id=body.subcategory_id,
            category_source=body.category_source,
            counterparty=body.counterparty,
            description=body.description,
            occurred_at=body.occurred_at,
            posted_at=body.posted_at,
            source=body.source,
            external_id=body.external_id,
            tags=body.tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TransactionResponse.model_validate(tx)


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions_endpoint(
    account_id: uuid.UUID | None = Query(default=None, description="Filter by account"),
    include_voided: bool = Query(default=False, description="Include voided transactions"),
    status_filter: FinancialTransactionStatus | None = Query(default=None, alias="status", description="Filter by status"),
    category_id: uuid.UUID | None = Query(default=None, description="Filter by category"),
    date_from: datetime | None = Query(default=None, description="Filter from date (inclusive)"),
    date_to: datetime | None = Query(default=None, description="Filter to date (inclusive)"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with filters. Voided transactions excluded by default."""
    items, total = await list_transactions(
        db, user.id,
        account_id=account_id,
        include_voided=include_voided,
        status_filter=status_filter,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(tx) for tx in items],
        total=total,
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction_endpoint(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single transaction by ID."""
    tx = await get_transaction(db, user.id, transaction_id)
    if tx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return TransactionResponse.model_validate(tx)


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
async def update_transaction_endpoint(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a transaction.
    Invariant F-02: amount must be positive if provided.
    Invariant F-11: creates audit history row on update.
    Status lifecycle: pending → posted → settled.
    """
    try:
        tx = await update_transaction(
            db, user.id, transaction_id,
            amount=body.amount,
            transaction_type=body.transaction_type,
            status=body.status,
            category_id=body.category_id if body.category_id is not None else ...,
            subcategory_id=body.subcategory_id if body.subcategory_id is not None else ...,
            category_source=body.category_source,
            counterparty=body.counterparty if body.counterparty is not None else ...,
            description=body.description if body.description is not None else ...,
            occurred_at=body.occurred_at,
            posted_at=body.posted_at if body.posted_at is not None else ...,
            tags=body.tags if body.tags is not None else ...,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TransactionResponse.model_validate(tx)


@router.post("/transactions/{transaction_id}/void", response_model=TransactionResponse)
async def void_transaction_endpoint(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Void a transaction (soft delete).
    Invariant F-11: creates audit history row on void.
    """
    try:
        tx = await void_transaction(db, user.id, transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TransactionResponse.model_validate(tx)


@router.get("/transactions/{transaction_id}/history", response_model=TransactionHistoryListResponse)
async def get_transaction_history_endpoint(
    transaction_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get audit trail for a transaction.
    Invariant F-11: Every mutation produces a history row.
    """
    try:
        items = await get_transaction_history(db, user.id, transaction_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return TransactionHistoryListResponse(
        items=[TransactionHistoryResponse.model_validate(h) for h in items],
        total=len(items),
    )


@router.get("/defaults/manual-entry", response_model=ManualEntryDefaults)
async def get_manual_entry_defaults_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get smart defaults for manual transaction entry.
    Section 5.2: most recently used account, date = today, status = posted.
    """
    result = await get_manual_entry_defaults(db, user.id)
    return ManualEntryDefaults(**result)
