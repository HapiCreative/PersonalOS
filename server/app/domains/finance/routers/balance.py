"""Balance snapshot and computation endpoints for the finance domain."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.balance import (
    BalanceReconcile,
    BalanceSnapshotCreate,
    BalanceSnapshotListResponse,
    BalanceSnapshotResponse,
    ComputedBalanceResponse,
)
from server.app.domains.finance.services.balance import (
    compute_account_balance,
    create_balance_snapshot,
    list_balance_snapshots,
    reconcile_balance_snapshot,
)

router = APIRouter()


@router.post("/balance-snapshots", response_model=BalanceSnapshotResponse, status_code=status.HTTP_201_CREATED)
async def create_balance_snapshot_endpoint(
    body: BalanceSnapshotCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a balance snapshot.
    Invariant F-09: computed snapshots never override reconciled ones.
    """
    try:
        snapshot = await create_balance_snapshot(
            db, user.id,
            account_id=body.account_id,
            balance=body.balance,
            currency=body.currency,
            snapshot_date=body.snapshot_date,
            source=body.source,
            is_reconciled=body.is_reconciled,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return BalanceSnapshotResponse.model_validate(snapshot)


@router.get("/balance-snapshots/{account_id}", response_model=BalanceSnapshotListResponse)
async def list_balance_snapshots_endpoint(
    account_id: uuid.UUID,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List balance snapshots for an account."""
    items, total = await list_balance_snapshots(db, user.id, account_id, limit, offset)
    return BalanceSnapshotListResponse(
        items=[BalanceSnapshotResponse.model_validate(s) for s in items],
        total=total,
    )


@router.get("/accounts/{account_id}/balance", response_model=ComputedBalanceResponse)
async def get_account_balance_endpoint(
    account_id: uuid.UUID,
    as_of_date: date | None = Query(default=None, description="Compute balance as of this date"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Compute the current balance for an account.
    Invariant F-08: only posted/settled transactions included.
    Invariant F-09: reconciled snapshot is authoritative.
    """
    try:
        result = await compute_account_balance(db, user.id, account_id, as_of_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Convert reconciled snapshot to response if present
    snapshot_response = None
    if result["last_reconciled_snapshot"] is not None:
        snapshot_response = BalanceSnapshotResponse.model_validate(result["last_reconciled_snapshot"])

    return ComputedBalanceResponse(
        account_id=result["account_id"],
        balance=result["balance"],
        currency=result["currency"],
        as_of_date=result["as_of_date"],
        last_reconciled_snapshot=snapshot_response,
        transactions_since_snapshot=result["transactions_since_snapshot"],
        is_computed=result["is_computed"],
    )


@router.put("/balance-snapshots/{snapshot_id}/reconcile", response_model=BalanceSnapshotResponse)
async def reconcile_balance_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    body: BalanceReconcile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark/unmark a balance snapshot as reconciled.
    Invariant F-09: reconciled snapshot = source of truth.
    """
    try:
        snapshot = await reconcile_balance_snapshot(db, user.id, snapshot_id, body.is_reconciled)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return BalanceSnapshotResponse.model_validate(snapshot)
