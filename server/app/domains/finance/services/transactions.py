"""Transaction CRUD and audit trail service functions for the finance domain."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    CategorySource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    NodeType,
    TransactionChangeType,
    TransactionSource,
)
from server.app.core.models.node import (
    FinancialTransaction,
    FinancialTransactionHistory,
    Node,
)
from server.app.domains.finance.services.categories import get_category


# Valid status transitions: pending → posted → settled
VALID_STATUS_TRANSITIONS: dict[FinancialTransactionStatus, list[FinancialTransactionStatus]] = {
    FinancialTransactionStatus.PENDING: [FinancialTransactionStatus.POSTED],
    FinancialTransactionStatus.POSTED: [FinancialTransactionStatus.SETTLED],
    FinancialTransactionStatus.SETTLED: [],  # Terminal state
}


async def create_transaction_history(
    db: AsyncSession,
    transaction: FinancialTransaction,
    change_type: TransactionChangeType,
    changed_by: uuid.UUID,
) -> FinancialTransactionHistory:
    """
    Invariant F-11: Every mutation to financial_transactions produces a history row.
    Captures full transaction state as JSONB snapshot.
    """
    # Get the current max version for this transaction
    version_stmt = (
        select(func.coalesce(func.max(FinancialTransactionHistory.version), 0))
        .where(FinancialTransactionHistory.transaction_id == transaction.id)
    )
    current_version = (await db.execute(version_stmt)).scalar_one()
    new_version = current_version + 1

    # Build full snapshot of current transaction state
    snapshot = {
        "id": str(transaction.id),
        "user_id": str(transaction.user_id),
        "account_id": str(transaction.account_id),
        "transaction_type": transaction.transaction_type.value,
        "status": transaction.status.value,
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "category_id": str(transaction.category_id) if transaction.category_id else None,
        "subcategory_id": str(transaction.subcategory_id) if transaction.subcategory_id else None,
        "category_source": transaction.category_source.value,
        "counterparty": transaction.counterparty,
        "description": transaction.description,
        "occurred_at": transaction.occurred_at.isoformat() if transaction.occurred_at else None,
        "posted_at": transaction.posted_at.isoformat() if transaction.posted_at else None,
        "source": transaction.source.value,
        "external_id": transaction.external_id,
        "transfer_group_id": str(transaction.transfer_group_id) if transaction.transfer_group_id else None,
        "tags": transaction.tags,
        "is_voided": transaction.is_voided,
    }

    history = FinancialTransactionHistory(
        transaction_id=transaction.id,
        version=new_version,
        snapshot=snapshot,
        change_type=change_type,
        changed_by=changed_by,
    )
    db.add(history)
    await db.flush()
    return history


async def get_transaction_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> list[FinancialTransactionHistory]:
    """Get audit trail for a transaction, enforcing ownership through the transaction."""
    # Verify transaction ownership
    tx_stmt = select(FinancialTransaction).where(
        FinancialTransaction.id == transaction_id,
        FinancialTransaction.user_id == user_id,
    )
    tx = (await db.execute(tx_stmt)).scalar_one_or_none()
    if tx is None:
        raise ValueError(f"Transaction {transaction_id} not found or not owned by user")

    stmt = (
        select(FinancialTransactionHistory)
        .where(FinancialTransactionHistory.transaction_id == transaction_id)
        .order_by(FinancialTransactionHistory.version.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    transaction_type: FinancialTransactionType,
    amount: Decimal,
    currency: str,
    status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED,
    category_id: uuid.UUID | None = None,
    subcategory_id: uuid.UUID | None = None,
    category_source: CategorySource = CategorySource.MANUAL,
    counterparty: str | None = None,
    description: str | None = None,
    occurred_at: datetime | None = None,
    posted_at: datetime | None = None,
    source: TransactionSource = TransactionSource.MANUAL,
    external_id: str | None = None,
    tags: list[str] | None = None,
    transfer_group_id: uuid.UUID | None = None,
) -> FinancialTransaction:
    """Create a financial transaction with audit trail (F-02, F-11)."""
    # Invariant F-02: amount always positive
    if amount <= 0:
        raise ValueError("Invariant F-02: amount must be positive, direction is encoded in transaction_type")

    # Verify account ownership
    acct_stmt = select(Node).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    acct = (await db.execute(acct_stmt)).scalar_one_or_none()
    if acct is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Validate category ownership if provided
    if category_id is not None:
        cat = await get_category(db, user_id, category_id)
        if cat is None:
            raise ValueError(f"Category {category_id} not found or not owned by user")

    if subcategory_id is not None:
        subcat = await get_category(db, user_id, subcategory_id)
        if subcat is None:
            raise ValueError(f"Subcategory {subcategory_id} not found or not owned by user")

    now = datetime.now(timezone.utc)
    if occurred_at is None:
        occurred_at = now

    transaction = FinancialTransaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=transaction_type,
        status=status,
        amount=amount,
        currency=currency,
        category_id=category_id,
        subcategory_id=subcategory_id,
        category_source=category_source,
        counterparty=counterparty,
        description=description,
        occurred_at=occurred_at,
        posted_at=posted_at,
        source=source,
        external_id=external_id,
        transfer_group_id=transfer_group_id,
        tags=tags,
        is_voided=False,
    )
    db.add(transaction)
    await db.flush()

    # Invariant F-11: create audit history row
    await create_transaction_history(db, transaction, TransactionChangeType.CREATE, user_id)

    return transaction


async def get_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> FinancialTransaction | None:
    """Get a transaction by ID, enforcing ownership."""
    stmt = select(FinancialTransaction).where(
        FinancialTransaction.id == transaction_id,
        FinancialTransaction.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None = None,
    include_voided: bool = False,
    status_filter: FinancialTransactionStatus | None = None,
    category_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FinancialTransaction], int]:
    """
    List transactions with filters. Voided transactions excluded by default.
    Invariant F-08: balance queries should filter by posted/settled status.
    """
    filters = [FinancialTransaction.user_id == user_id]

    if account_id is not None:
        filters.append(FinancialTransaction.account_id == account_id)

    if not include_voided:
        filters.append(FinancialTransaction.is_voided == False)  # noqa: E712

    if status_filter is not None:
        filters.append(FinancialTransaction.status == status_filter)

    if category_id is not None:
        filters.append(FinancialTransaction.category_id == category_id)

    if date_from is not None:
        filters.append(FinancialTransaction.occurred_at >= date_from)

    if date_to is not None:
        filters.append(FinancialTransaction.occurred_at <= date_to)

    count_stmt = (
        select(func.count())
        .select_from(FinancialTransaction)
        .where(*filters)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(FinancialTransaction)
        .where(*filters)
        .order_by(FinancialTransaction.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def update_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    amount: Decimal | None = None,
    transaction_type: FinancialTransactionType | None = None,
    status: FinancialTransactionStatus | None = None,
    category_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    subcategory_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    category_source: CategorySource | None = None,
    counterparty: str | None = ...,  # type: ignore[assignment]
    description: str | None = ...,  # type: ignore[assignment]
    occurred_at: datetime | None = None,
    posted_at: datetime | None = ...,  # type: ignore[assignment]
    tags: list[str] | None = ...,  # type: ignore[assignment]
) -> FinancialTransaction:
    """Update a financial transaction (F-02, F-11). Status lifecycle: pending → posted → settled."""
    tx = await get_transaction(db, user_id, transaction_id)
    if tx is None:
        raise ValueError(f"Transaction {transaction_id} not found or not owned by user")

    if tx.is_voided:
        raise ValueError("Cannot update a voided transaction")

    # Invariant F-02: amount always positive
    if amount is not None:
        if amount <= 0:
            raise ValueError("Invariant F-02: amount must be positive")
        tx.amount = amount

    if transaction_type is not None:
        tx.transaction_type = transaction_type

    # Status lifecycle validation: pending → posted → settled
    if status is not None and status != tx.status:
        if status not in VALID_STATUS_TRANSITIONS.get(tx.status, []):
            raise ValueError(
                f"Invalid status transition: {tx.status.value} → {status.value}. "
                f"Valid transitions: {[s.value for s in VALID_STATUS_TRANSITIONS.get(tx.status, [])]}"
            )
        tx.status = status

    if category_id is not ...:
        if category_id is not None:
            cat = await get_category(db, user_id, category_id)
            if cat is None:
                raise ValueError(f"Category {category_id} not found or not owned by user")
        tx.category_id = category_id

    if subcategory_id is not ...:
        if subcategory_id is not None:
            subcat = await get_category(db, user_id, subcategory_id)
            if subcat is None:
                raise ValueError(f"Subcategory {subcategory_id} not found or not owned by user")
        tx.subcategory_id = subcategory_id

    if category_source is not None:
        tx.category_source = category_source

    if counterparty is not ...:
        tx.counterparty = counterparty

    if description is not ...:
        tx.description = description

    if occurred_at is not None:
        tx.occurred_at = occurred_at

    if posted_at is not ...:
        tx.posted_at = posted_at

    if tags is not ...:
        tx.tags = tags

    tx.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Invariant F-11: create audit history row on update
    await create_transaction_history(db, tx, TransactionChangeType.UPDATE, user_id)

    return tx


async def void_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> FinancialTransaction:
    """Void a transaction (soft delete, F-11). Excluded from balance calculations."""
    tx = await get_transaction(db, user_id, transaction_id)
    if tx is None:
        raise ValueError(f"Transaction {transaction_id} not found or not owned by user")

    if tx.is_voided:
        raise ValueError("Transaction is already voided")

    tx.is_voided = True
    tx.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Invariant F-11: create audit history row on void
    await create_transaction_history(db, tx, TransactionChangeType.VOID, user_id)

    return tx


async def get_manual_entry_defaults(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """Get smart defaults for manual transaction entry (Section 5.2)."""
    # Find the most recently used account (by most recent transaction)
    last_tx_stmt = (
        select(FinancialTransaction.account_id)
        .where(FinancialTransaction.user_id == user_id)
        .order_by(FinancialTransaction.created_at.desc())
        .limit(1)
    )
    last_account_id = (await db.execute(last_tx_stmt)).scalar_one_or_none()

    last_account_title = None
    if last_account_id is not None:
        acct_stmt = select(Node.title).where(Node.id == last_account_id)
        last_account_title = (await db.execute(acct_stmt)).scalar_one_or_none()

    return {
        "last_used_account_id": last_account_id,
        "last_used_account_title": last_account_title,
        "default_date": date.today(),
        "default_status": FinancialTransactionStatus.POSTED,
    }
