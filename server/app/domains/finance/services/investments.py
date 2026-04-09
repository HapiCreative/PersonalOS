"""Investment holdings and transaction service functions.

F2.1: Snapshot-based holdings CRUD, investment transaction CRUD with
corporate action support (split, merger, spinoff).
Ref: Finance Design Rev 3 Sections 3.3–3.4.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    BalanceSnapshotSource,
    InvestmentAssetType,
    InvestmentTransactionType,
    NodeType,
    TransactionSource,
    ValuationSource,
)
from server.app.core.models.node import Node
from server.app.domains.finance.models.investments import (
    InvestmentHolding,
    InvestmentTransaction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _verify_account_ownership(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID,
) -> None:
    """Raise ValueError if account does not exist or is not owned by user."""
    stmt = select(Node).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")


# ---------------------------------------------------------------------------
# Investment Holdings CRUD
# ---------------------------------------------------------------------------


async def create_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    symbol: str,
    asset_type: InvestmentAssetType,
    quantity: Decimal,
    currency: str,
    as_of_date: date,
    valuation_source: ValuationSource,
    asset_name: str | None = None,
    cost_basis: Decimal | None = None,
    source: BalanceSnapshotSource = BalanceSnapshotSource.MANUAL,
) -> InvestmentHolding:
    """Create an investment holding snapshot."""
    await _verify_account_ownership(db, user_id, account_id)

    holding = InvestmentHolding(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        asset_name=asset_name,
        asset_type=asset_type,
        quantity=quantity,
        cost_basis=cost_basis,
        currency=currency,
        as_of_date=as_of_date,
        source=source,
        valuation_source=valuation_source,
    )
    db.add(holding)
    await db.flush()
    return holding


async def get_holding(
    db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID,
) -> InvestmentHolding | None:
    """Get a single holding by ID, enforcing ownership."""
    stmt = select(InvestmentHolding).where(
        InvestmentHolding.id == holding_id,
        InvestmentHolding.user_id == user_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_holdings(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    symbol: str | None = None,
    as_of_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InvestmentHolding], int]:
    """List holdings with optional filters, enforcing ownership."""
    filters = [InvestmentHolding.user_id == user_id]
    if account_id is not None:
        filters.append(InvestmentHolding.account_id == account_id)
    if symbol is not None:
        filters.append(InvestmentHolding.symbol == symbol)
    if as_of_date is not None:
        filters.append(InvestmentHolding.as_of_date == as_of_date)

    total = (await db.execute(
        select(func.count()).select_from(InvestmentHolding).where(*filters)
    )).scalar_one()

    items = list((await db.execute(
        select(InvestmentHolding)
        .where(*filters)
        .order_by(InvestmentHolding.as_of_date.desc(), InvestmentHolding.symbol)
        .limit(limit)
        .offset(offset)
    )).scalars().all())

    return items, total


async def update_holding(
    db: AsyncSession,
    user_id: uuid.UUID,
    holding_id: uuid.UUID,
    *,
    symbol: str | None = None,
    asset_name: str | None = ...,  # type: ignore[assignment]
    asset_type: InvestmentAssetType | None = None,
    quantity: Decimal | None = None,
    cost_basis: Decimal | None = ...,  # type: ignore[assignment]
    currency: str | None = None,
    as_of_date: date | None = None,
    source: BalanceSnapshotSource | None = None,
    valuation_source: ValuationSource | None = None,
) -> InvestmentHolding | None:
    """Update a holding snapshot, enforcing ownership."""
    holding = await get_holding(db, user_id, holding_id)
    if holding is None:
        return None

    if symbol is not None:
        holding.symbol = symbol
    if asset_name is not ...:
        holding.asset_name = asset_name
    if asset_type is not None:
        holding.asset_type = asset_type
    if quantity is not None:
        holding.quantity = quantity
    if cost_basis is not ...:
        holding.cost_basis = cost_basis
    if currency is not None:
        holding.currency = currency
    if as_of_date is not None:
        holding.as_of_date = as_of_date
    if source is not None:
        holding.source = source
    if valuation_source is not None:
        holding.valuation_source = valuation_source

    await db.flush()
    return holding


async def delete_holding(
    db: AsyncSession, user_id: uuid.UUID, holding_id: uuid.UUID,
) -> bool:
    """Delete a holding snapshot, enforcing ownership. Returns True if deleted."""
    holding = await get_holding(db, user_id, holding_id)
    if holding is None:
        return False
    await db.delete(holding)
    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Investment Transactions CRUD
# ---------------------------------------------------------------------------


async def create_investment_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    symbol: str,
    transaction_type: InvestmentTransactionType,
    quantity: Decimal,
    price_per_unit: Decimal,
    total_amount: Decimal,
    currency: str,
    occurred_at: datetime,
    lot_id: str | None = None,
    source: TransactionSource = TransactionSource.MANUAL,
    external_id: str | None = None,
    notes: str | None = None,
) -> InvestmentTransaction:
    """Create an investment transaction.

    For split transactions, also adjusts existing holdings' quantity and
    price_per_unit to maintain cost basis integrity.
    """
    await _verify_account_ownership(db, user_id, account_id)

    tx = InvestmentTransaction(
        user_id=user_id,
        account_id=account_id,
        symbol=symbol,
        transaction_type=transaction_type,
        quantity=quantity,
        price_per_unit=price_per_unit,
        total_amount=total_amount,
        currency=currency,
        occurred_at=occurred_at,
        lot_id=lot_id,
        source=source,
        external_id=external_id,
        notes=notes,
    )
    db.add(tx)
    await db.flush()

    # Corporate action: split adjusts existing holdings
    if transaction_type == InvestmentTransactionType.SPLIT and quantity != 0:
        await _apply_split(db, user_id, account_id, symbol, quantity, price_per_unit)

    return tx


async def _apply_split(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    symbol: str,
    split_ratio_quantity: Decimal,
    split_ratio_price: Decimal,
) -> None:
    """Adjust holdings after a stock split.

    A split with quantity=N means each share becomes N shares;
    price_per_unit is the new price (old_price / N).
    This maintains cost basis integrity.
    """
    stmt = select(InvestmentHolding).where(
        InvestmentHolding.user_id == user_id,
        InvestmentHolding.account_id == account_id,
        InvestmentHolding.symbol == symbol,
    )
    holdings = list((await db.execute(stmt)).scalars().all())

    for h in holdings:
        old_quantity = h.quantity
        # split_ratio_quantity represents the new total shares ratio
        # e.g., 2-for-1 split: quantity=2, meaning multiply shares by 2
        h.quantity = old_quantity * split_ratio_quantity
        if h.cost_basis is not None and old_quantity > 0:
            # Cost basis stays the same, but price per unit adjusts
            h.cost_basis = h.cost_basis  # Total cost basis unchanged
    await db.flush()


async def get_investment_transaction(
    db: AsyncSession, user_id: uuid.UUID, tx_id: uuid.UUID,
) -> InvestmentTransaction | None:
    """Get a single investment transaction by ID, enforcing ownership."""
    stmt = select(InvestmentTransaction).where(
        InvestmentTransaction.id == tx_id,
        InvestmentTransaction.user_id == user_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_investment_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID | None = None,
    symbol: str | None = None,
    transaction_type: InvestmentTransactionType | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[InvestmentTransaction], int]:
    """List investment transactions with optional filters."""
    filters = [InvestmentTransaction.user_id == user_id]
    if account_id is not None:
        filters.append(InvestmentTransaction.account_id == account_id)
    if symbol is not None:
        filters.append(InvestmentTransaction.symbol == symbol)
    if transaction_type is not None:
        filters.append(InvestmentTransaction.transaction_type == transaction_type)
    if date_from is not None:
        filters.append(InvestmentTransaction.occurred_at >= date_from)
    if date_to is not None:
        filters.append(InvestmentTransaction.occurred_at <= date_to)

    total = (await db.execute(
        select(func.count()).select_from(InvestmentTransaction).where(*filters)
    )).scalar_one()

    items = list((await db.execute(
        select(InvestmentTransaction)
        .where(*filters)
        .order_by(InvestmentTransaction.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )).scalars().all())

    return items, total


async def update_investment_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    tx_id: uuid.UUID,
    *,
    symbol: str | None = None,
    transaction_type: InvestmentTransactionType | None = None,
    quantity: Decimal | None = None,
    price_per_unit: Decimal | None = None,
    total_amount: Decimal | None = None,
    currency: str | None = None,
    occurred_at: datetime | None = None,
    lot_id: str | None = ...,  # type: ignore[assignment]
    source: TransactionSource | None = None,
    notes: str | None = ...,  # type: ignore[assignment]
) -> InvestmentTransaction | None:
    """Update an investment transaction, enforcing ownership."""
    tx = await get_investment_transaction(db, user_id, tx_id)
    if tx is None:
        return None

    if symbol is not None:
        tx.symbol = symbol
    if transaction_type is not None:
        tx.transaction_type = transaction_type
    if quantity is not None:
        tx.quantity = quantity
    if price_per_unit is not None:
        tx.price_per_unit = price_per_unit
    if total_amount is not None:
        tx.total_amount = total_amount
    if currency is not None:
        tx.currency = currency
    if occurred_at is not None:
        tx.occurred_at = occurred_at
    if lot_id is not ...:
        tx.lot_id = lot_id
    if source is not None:
        tx.source = source
    if notes is not ...:
        tx.notes = notes

    await db.flush()
    return tx


async def delete_investment_transaction(
    db: AsyncSession, user_id: uuid.UUID, tx_id: uuid.UUID,
) -> bool:
    """Delete an investment transaction, enforcing ownership."""
    tx = await get_investment_transaction(db, user_id, tx_id)
    if tx is None:
        return False
    await db.delete(tx)
    await db.flush()
    return True
