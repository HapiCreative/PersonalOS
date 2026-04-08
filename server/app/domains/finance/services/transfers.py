"""Transfer pairing service functions for the finance domain."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    FinancialTransactionStatus,
    FinancialTransactionType,
    NodeType,
    TransactionSource,
)
from server.app.core.models.node import FinancialTransaction, Node
from server.app.domains.finance.services.transactions import create_transaction


async def create_transfer(
    db: AsyncSession,
    user_id: uuid.UUID,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    description: str | None = None,
    occurred_at: datetime | None = None,
    status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED,
    tags: list[str] | None = None,
) -> tuple[FinancialTransaction, FinancialTransaction]:
    """
    Create a paired transfer: 1 transfer_out + 1 transfer_in.
    Invariant F-05: exactly 2 records per transfer_group_id.
    Invariant F-02: amount always positive.
    Invariant F-11: audit history for both transactions.
    """
    # Invariant F-02: amount must be positive
    if amount <= 0:
        raise ValueError("Invariant F-02: transfer amount must be positive")

    if from_account_id == to_account_id:
        raise ValueError("Transfer source and destination accounts must be different")

    # Verify both accounts exist and are owned by user
    for acct_id in [from_account_id, to_account_id]:
        acct_stmt = select(Node).where(
            Node.id == acct_id,
            Node.owner_id == user_id,
            Node.type == NodeType.ACCOUNT,
        )
        acct = (await db.execute(acct_stmt)).scalar_one_or_none()
        if acct is None:
            raise ValueError(f"Account {acct_id} not found or not owned by user")

    # Invariant F-05: generate a single transfer_group_id for the pair
    transfer_group_id = uuid.uuid4()

    now = datetime.now(timezone.utc)
    if occurred_at is None:
        occurred_at = now

    # Create transfer_out transaction
    tx_out = await create_transaction(
        db, user_id,
        account_id=from_account_id,
        transaction_type=FinancialTransactionType.TRANSFER_OUT,
        amount=amount,
        currency=currency,
        status=status,
        description=description,
        occurred_at=occurred_at,
        source=TransactionSource.MANUAL,
        transfer_group_id=transfer_group_id,
        tags=tags,
    )

    # Create transfer_in transaction
    tx_in = await create_transaction(
        db, user_id,
        account_id=to_account_id,
        transaction_type=FinancialTransactionType.TRANSFER_IN,
        amount=amount,
        currency=currency,
        status=status,
        description=description,
        occurred_at=occurred_at,
        source=TransactionSource.MANUAL,
        transfer_group_id=transfer_group_id,
        tags=tags,
    )

    return tx_out, tx_in


async def detect_orphan_transfers(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """
    Invariant F-05: Detect transfer_group_ids with count != 2.
    Returns list of orphaned transfer_group_ids.
    """
    stmt = (
        select(FinancialTransaction.transfer_group_id)
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.transfer_group_id.isnot(None),
            FinancialTransaction.is_voided == False,  # noqa: E712
        )
        .group_by(FinancialTransaction.transfer_group_id)
        .having(func.count() != 2)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def get_transfer_pair(
    db: AsyncSession,
    user_id: uuid.UUID,
    transfer_group_id: uuid.UUID,
) -> list[FinancialTransaction]:
    """Get both transactions in a transfer pair by transfer_group_id."""
    stmt = (
        select(FinancialTransaction)
        .where(
            FinancialTransaction.user_id == user_id,
            FinancialTransaction.transfer_group_id == transfer_group_id,
        )
        .order_by(FinancialTransaction.transaction_type.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
