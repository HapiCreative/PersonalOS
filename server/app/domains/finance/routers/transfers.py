"""Transfer endpoints for the finance domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.transactions import TransactionResponse
from server.app.domains.finance.schemas.transfers import TransferCreate, TransferResponse
from server.app.domains.finance.services.transfers import (
    create_transfer,
    detect_orphan_transfers,
    get_transfer_pair,
)

router = APIRouter()


@router.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_201_CREATED)
async def create_transfer_endpoint(
    body: TransferCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a paired transfer (transfer_out + transfer_in).
    Invariant F-05: exactly 2 records per transfer_group_id.
    Invariant F-02: amount must be positive.
    """
    try:
        tx_out, tx_in = await create_transfer(
            db, user.id,
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=body.amount,
            currency=body.currency,
            description=body.description,
            occurred_at=body.occurred_at,
            status=body.status,
            tags=body.tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return TransferResponse(
        transfer_group_id=tx_out.transfer_group_id,
        transfer_out=TransactionResponse.model_validate(tx_out),
        transfer_in=TransactionResponse.model_validate(tx_in),
    )


@router.get("/transfers/orphans", response_model=list[uuid.UUID])
async def detect_orphan_transfers_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect orphaned transfers (transfer_group_ids with count != 2).
    Invariant F-05: exactly 2 records per transfer_group_id.
    """
    return await detect_orphan_transfers(db, user.id)


@router.get("/transfers/{transfer_group_id}", response_model=list[TransactionResponse])
async def get_transfer_pair_endpoint(
    transfer_group_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get both transactions in a transfer pair."""
    items = await get_transfer_pair(db, user.id, transfer_group_id)
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transfer pair not found")
    return [TransactionResponse.model_validate(tx) for tx in items]
