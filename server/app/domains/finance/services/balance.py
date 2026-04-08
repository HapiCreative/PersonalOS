"""Balance snapshot and computation service functions for the finance domain."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    BalanceSnapshotSource,
    FinancialTransactionStatus,
    NodeType,
)
from server.app.core.models.node import AccountNode, BalanceSnapshot, FinancialTransaction, Node


async def create_balance_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    balance: Decimal,
    currency: str,
    snapshot_date: date,
    source: BalanceSnapshotSource = BalanceSnapshotSource.MANUAL,
    is_reconciled: bool = False,
) -> BalanceSnapshot:
    """
    Create a balance snapshot.
    Invariant F-09: Reconciled snapshots are authoritative.
    Computed snapshots must never override reconciled ones.
    """
    # Verify account ownership
    acct_stmt = (
        select(Node)
        .where(Node.id == account_id, Node.owner_id == user_id, Node.type == NodeType.ACCOUNT)
    )
    acct = (await db.execute(acct_stmt)).scalar_one_or_none()
    if acct is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Invariant F-09: Check if a reconciled snapshot already exists for this date
    existing_stmt = select(BalanceSnapshot).where(
        BalanceSnapshot.account_id == account_id,
        BalanceSnapshot.snapshot_date == snapshot_date,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is not None:
        if existing.is_reconciled and source == BalanceSnapshotSource.COMPUTED:
            raise ValueError(
                "Invariant F-09: Cannot override reconciled snapshot with computed balance"
            )
        # Update existing snapshot
        existing.balance = balance
        existing.currency = currency
        existing.source = source
        if is_reconciled:
            existing.is_reconciled = True
            existing.reconciled_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    snapshot = BalanceSnapshot(
        user_id=user_id,
        account_id=account_id,
        balance=balance,
        currency=currency,
        snapshot_date=snapshot_date,
        source=source,
        is_reconciled=is_reconciled,
        reconciled_at=datetime.now(timezone.utc) if is_reconciled else None,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def list_balance_snapshots(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[BalanceSnapshot], int]:
    """List balance snapshots for an account, enforcing ownership."""
    base_filter = [
        BalanceSnapshot.user_id == user_id,
        BalanceSnapshot.account_id == account_id,
    ]

    count_stmt = (
        select(func.count())
        .select_from(BalanceSnapshot)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(BalanceSnapshot)
        .where(*base_filter)
        .order_by(BalanceSnapshot.snapshot_date.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def compute_account_balance(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    as_of_date: date | None = None,
) -> dict:
    """
    Compute the current balance for an account.
    Invariant F-08: only include posted/settled transactions in balance.
    Invariant F-09: reconciled snapshot is authoritative.

    Algorithm:
    1. Find the most recent reconciled snapshot on or before as_of_date.
    2. If found, add SUM(signed_amount) of posted/settled, non-voided transactions since that snapshot.
    3. If no reconciled snapshot, find the most recent snapshot of any type on or before as_of_date.
    4. If no snapshot at all, sum all posted/settled, non-voided transactions.
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Verify account ownership
    acct_stmt = select(Node, AccountNode).join(
        AccountNode, AccountNode.node_id == Node.id
    ).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    acct_result = await db.execute(acct_stmt)
    acct_row = acct_result.one_or_none()
    if acct_row is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    _, account_node = acct_row

    # Invariant F-09: Look for the most recent reconciled snapshot first
    reconciled_stmt = (
        select(BalanceSnapshot)
        .where(
            BalanceSnapshot.account_id == account_id,
            BalanceSnapshot.user_id == user_id,
            BalanceSnapshot.snapshot_date <= as_of_date,
            BalanceSnapshot.is_reconciled == True,  # noqa: E712
        )
        .order_by(BalanceSnapshot.snapshot_date.desc())
        .limit(1)
    )
    reconciled_snapshot = (await db.execute(reconciled_stmt)).scalar_one_or_none()

    # Fall back to any snapshot if no reconciled one
    base_snapshot = reconciled_snapshot
    if base_snapshot is None:
        any_snapshot_stmt = (
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.account_id == account_id,
                BalanceSnapshot.user_id == user_id,
                BalanceSnapshot.snapshot_date <= as_of_date,
            )
            .order_by(BalanceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        base_snapshot = (await db.execute(any_snapshot_stmt)).scalar_one_or_none()

    # Invariant F-08: Sum signed_amount for posted/settled, non-voided transactions
    tx_filters = [
        FinancialTransaction.account_id == account_id,
        FinancialTransaction.user_id == user_id,
        FinancialTransaction.is_voided == False,  # noqa: E712
        FinancialTransaction.status.in_([
            FinancialTransactionStatus.POSTED,
            FinancialTransactionStatus.SETTLED,
        ]),
    ]

    if base_snapshot is not None:
        # Only transactions after the snapshot date
        tx_filters.append(FinancialTransaction.occurred_at > datetime.combine(
            base_snapshot.snapshot_date, datetime.min.time(), tzinfo=timezone.utc
        ))

    # Also limit to as_of_date
    tx_filters.append(FinancialTransaction.occurred_at <= datetime.combine(
        as_of_date, datetime.max.time(), tzinfo=timezone.utc
    ))

    sum_stmt = (
        select(
            func.coalesce(func.sum(FinancialTransaction.signed_amount), Decimal("0")),
            func.count(),
        )
        .where(*tx_filters)
    )
    sum_result = await db.execute(sum_stmt)
    row = sum_result.one()
    tx_sum = row[0]
    tx_count = row[1]

    if base_snapshot is not None:
        balance = base_snapshot.balance + tx_sum
        is_computed = True
    else:
        balance = tx_sum
        is_computed = True

    if reconciled_snapshot is not None and tx_count == 0:
        # Direct reconciled snapshot with no transactions since — not computed
        is_computed = False

    return {
        "account_id": account_id,
        "balance": balance,
        "currency": account_node.currency,
        "as_of_date": as_of_date,
        "last_reconciled_snapshot": reconciled_snapshot,
        "transactions_since_snapshot": tx_count,
        "is_computed": is_computed,
    }


async def reconcile_balance_snapshot(
    db: AsyncSession,
    user_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    is_reconciled: bool = True,
) -> BalanceSnapshot:
    """
    Mark a balance snapshot as reconciled.
    Invariant F-09: reconciled snapshot = source of truth.
    """
    stmt = select(BalanceSnapshot).where(
        BalanceSnapshot.id == snapshot_id,
        BalanceSnapshot.user_id == user_id,
    )
    snapshot = (await db.execute(stmt)).scalar_one_or_none()
    if snapshot is None:
        raise ValueError(f"Balance snapshot {snapshot_id} not found or not owned by user")

    snapshot.is_reconciled = is_reconciled
    if is_reconciled:
        snapshot.reconciled_at = datetime.now(timezone.utc)
    else:
        snapshot.reconciled_at = None

    await db.flush()
    return snapshot
