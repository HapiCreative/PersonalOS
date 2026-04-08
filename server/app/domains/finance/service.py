"""
Finance domain service (Finance Design Rev 3, Sections 2.1–2.6, 3.1–3.2, 3.6, 5.2–5.3).
Backend Core Services for accounts, categories, allocations, balance snapshots, audit trail,
transaction CRUD, transfer pairing, balance computation, CSV import, and smart defaults.

Invariants enforced:
- F-01: Transactions never become nodes (architectural constraint)
- F-02: amount always positive, direction in transaction_type (application + DB CHECK)
- F-03: Financial goal field consistency (application layer, primary)
- F-05: Transfer pairing — exactly 2 records per transfer_group_id (application layer)
- F-06: No shadow graph — relationships are edges + allocations only
- F-08: Balance queries use posted/settled only (application layer)
- F-09: Reconciled snapshots are authoritative, never overridden by computed
- F-11: Every financial_transaction mutation → history row (application layer)
- F-12: Category deletion blocked if transactions reference it (DB RESTRICT + app check)
- F-13: Percentage allocation sum ≤ 1.0 per account across all goals (application layer, primary)
"""

import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    AccountType,
    AllocationType,
    BalanceSnapshotSource,
    CategorySource,
    EdgeRelationType,
    EdgeOrigin,
    EdgeState,
    FinancialTransactionStatus,
    FinancialTransactionType,
    GoalType,
    NodeType,
    TransactionChangeType,
    TransactionSource,
)
from server.app.core.models.node import (
    AccountNode,
    BalanceSnapshot,
    CsvImportMapping,
    FinancialCategory,
    FinancialTransaction,
    FinancialTransactionHistory,
    GoalAllocation,
    GoalNode,
    Node,
)


# =============================================================================
# Account Service
# =============================================================================


async def create_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    title: str,
    account_type: AccountType,
    currency: str,
    summary: str | None = None,
    institution: str | None = None,
    account_number_masked: str | None = None,
    notes: str | None = None,
) -> tuple[Node, AccountNode]:
    """
    Create an account (Core node + account_nodes companion in single transaction).
    Section 2.1: Accounts are durable, user-owned entities.
    """
    node = Node(
        type=NodeType.ACCOUNT,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    account = AccountNode(
        node_id=node.id,
        account_type=account_type,
        institution=institution,
        currency=currency,
        account_number_masked=account_number_masked,
        is_active=True,
        notes=notes,
    )
    db.add(account)
    await db.flush()

    return node, account


async def get_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, AccountNode] | None:
    """Get an account by node ID, enforcing ownership."""
    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, account = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()

    return node, account


async def list_accounts(
    db: AsyncSession,
    owner_id: uuid.UUID,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, AccountNode]], int]:
    """List accounts with optional active/inactive filter, enforcing ownership."""
    base_filter = [Node.owner_id == owner_id, Node.type == NodeType.ACCOUNT]

    if is_active is not None:
        base_filter.append(AccountNode.is_active == is_active)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(*base_filter)
        .order_by(Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.all())

    return items, total


async def update_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    title: str | None = None,
    summary: str | None = ...,  # type: ignore[assignment]
    account_type: AccountType | None = None,
    institution: str | None = ...,  # type: ignore[assignment]
    currency: str | None = None,
    account_number_masked: str | None = ...,  # type: ignore[assignment]
    is_active: bool | None = None,
    notes: str | None = ...,  # type: ignore[assignment]
) -> tuple[Node, AccountNode] | None:
    """Update account fields, enforcing ownership."""
    pair = await get_account(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, account = pair

    if title is not None:
        node.title = title
    if summary is not ...:
        node.summary = summary
    if account_type is not None:
        account.account_type = account_type
    if institution is not ...:
        account.institution = institution
    if currency is not None:
        account.currency = currency
    if account_number_masked is not ...:
        account.account_number_masked = account_number_masked
    if is_active is not None:
        account.is_active = is_active
    if notes is not ...:
        account.notes = notes

    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, account


async def deactivate_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, AccountNode] | None:
    """Soft deactivate an account (set is_active = false)."""
    pair = await get_account(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, account = pair
    account.is_active = False
    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, account


# =============================================================================
# Category Service
# =============================================================================


SYSTEM_DEFAULT_CATEGORIES = [
    ("Groceries", 1),
    ("Rent/Mortgage", 2),
    ("Utilities", 3),
    ("Dining", 4),
    ("Transportation", 5),
    ("Entertainment", 6),
    ("Healthcare", 7),
    ("Insurance", 8),
    ("Subscriptions", 9),
    ("Personal Care", 10),
    ("Education", 11),
    ("Gifts/Donations", 12),
    ("Income", 13),
    ("Investments", 14),
    ("Fees", 15),
    ("Other", 16),
]


async def seed_categories_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[FinancialCategory]:
    """
    Seed system default categories for a user.
    Section 2.5: System-seeded defaults created on user creation.
    Idempotent — skips duplicates via conflict detection.
    """
    categories = []
    for name, sort_order in SYSTEM_DEFAULT_CATEGORIES:
        # Check if already exists
        stmt = select(FinancialCategory).where(
            FinancialCategory.user_id == user_id,
            FinancialCategory.name == name,
            FinancialCategory.parent_id.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            categories.append(existing)
            continue

        cat = FinancialCategory(
            user_id=user_id,
            name=name,
            is_system=True,
            sort_order=sort_order,
        )
        db.add(cat)
        categories.append(cat)

    await db.flush()
    return categories


async def create_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    parent_id: uuid.UUID | None = None,
    icon: str | None = None,
    sort_order: int = 0,
) -> FinancialCategory:
    """Create a user financial category. User-created categories have is_system=false."""
    # Validate parent exists and belongs to user if specified
    if parent_id is not None:
        parent = await get_category(db, user_id, parent_id)
        if parent is None:
            raise ValueError(f"Parent category {parent_id} not found or not owned by user")

    cat = FinancialCategory(
        user_id=user_id,
        name=name,
        parent_id=parent_id,
        icon=icon,
        is_system=False,
        sort_order=sort_order,
    )
    db.add(cat)
    await db.flush()
    return cat


async def get_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> FinancialCategory | None:
    """Get a category by ID, enforcing ownership."""
    stmt = select(FinancialCategory).where(
        FinancialCategory.id == category_id,
        FinancialCategory.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_categories(
    db: AsyncSession,
    user_id: uuid.UUID,
    parent_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[FinancialCategory], int]:
    """List categories with optional parent filter, enforcing ownership."""
    base_filter = [FinancialCategory.user_id == user_id]

    if parent_id is not ...:
        if parent_id is None:
            base_filter.append(FinancialCategory.parent_id.is_(None))
        else:
            base_filter.append(FinancialCategory.parent_id == parent_id)

    count_stmt = (
        select(func.count())
        .select_from(FinancialCategory)
        .where(*base_filter)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(FinancialCategory)
        .where(*base_filter)
        .order_by(FinancialCategory.sort_order.asc(), FinancialCategory.name.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return items, total


async def list_categories_tree(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[FinancialCategory]:
    """List all categories for a user (for building hierarchy tree in app layer)."""
    stmt = (
        select(FinancialCategory)
        .where(FinancialCategory.user_id == user_id)
        .order_by(FinancialCategory.sort_order.asc(), FinancialCategory.name.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    name: str | None = None,
    parent_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    icon: str | None = ...,  # type: ignore[assignment]
    sort_order: int | None = None,
) -> FinancialCategory | None:
    """Update a category, enforcing ownership."""
    cat = await get_category(db, user_id, category_id)
    if cat is None:
        return None

    if name is not None:
        cat.name = name
    if parent_id is not ...:
        # Validate parent if setting one
        if parent_id is not None:
            parent = await get_category(db, user_id, parent_id)
            if parent is None:
                raise ValueError(f"Parent category {parent_id} not found or not owned by user")
            # Prevent self-referencing
            if parent_id == category_id:
                raise ValueError("Category cannot be its own parent")
        cat.parent_id = parent_id
    if icon is not ...:
        cat.icon = icon
    if sort_order is not None:
        cat.sort_order = sort_order

    await db.flush()
    return cat


async def delete_category(
    db: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
) -> bool:
    """
    Delete a category. Invariant F-12: blocked if transactions reference it.
    DB enforces via RESTRICT FK, but we check at app layer first for a clear error.
    """
    cat = await get_category(db, user_id, category_id)
    if cat is None:
        return False

    # Invariant F-12: Check if any transactions reference this category
    tx_count_stmt = (
        select(func.count())
        .select_from(FinancialTransaction)
        .where(FinancialTransaction.category_id == category_id)
    )
    tx_count = (await db.execute(tx_count_stmt)).scalar_one()
    if tx_count > 0:
        raise ValueError(
            f"Invariant F-12: Cannot delete category '{cat.name}' — "
            f"{tx_count} transaction(s) reference it"
        )

    # Also check subcategory references
    sub_count_stmt = (
        select(func.count())
        .select_from(FinancialTransaction)
        .where(FinancialTransaction.subcategory_id == category_id)
    )
    sub_count = (await db.execute(sub_count_stmt)).scalar_one()
    if sub_count > 0:
        raise ValueError(
            f"Invariant F-12: Cannot delete category '{cat.name}' — "
            f"{sub_count} transaction(s) reference it as subcategory"
        )

    await db.delete(cat)
    await db.flush()
    return True


# =============================================================================
# Allocation Service
# =============================================================================


async def create_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_id: uuid.UUID,
    account_id: uuid.UUID,
    allocation_type: AllocationType,
    value: Decimal,
) -> GoalAllocation:
    """
    Create a goal allocation.
    Invariant F-06: No shadow graph — relationships are edges + allocations only.
    Invariant F-13: For percentage allocations, SUM ≤ 1.0 per account across all goals.

    Also ensures that a corresponding account_funds_goal edge exists (F-06).
    """
    # Validate goal exists and is financial, owned by user
    goal_stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(Node.id == goal_id, Node.owner_id == owner_id)
    )
    goal_result = await db.execute(goal_stmt)
    goal_row = goal_result.one_or_none()
    if goal_row is None:
        raise ValueError(f"Goal {goal_id} not found or not owned by user")

    _, goal_node = goal_row
    # Invariant F-03: allocation only makes sense for financial goals
    if goal_node.goal_type != GoalType.FINANCIAL:
        raise ValueError("Invariant F-03: Allocations can only be created for financial goals")

    # Validate account exists and is owned by user
    acct_stmt = (
        select(Node, AccountNode)
        .join(AccountNode, AccountNode.node_id == Node.id)
        .where(Node.id == account_id, Node.owner_id == owner_id)
    )
    acct_result = await db.execute(acct_stmt)
    acct_row = acct_result.one_or_none()
    if acct_row is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Validate value constraints
    if allocation_type == AllocationType.PERCENTAGE:
        if value < 0 or value > 1:
            raise ValueError("Percentage allocation value must be between 0.0 and 1.0")

        # Invariant F-13: Check sum of percentage allocations for this account
        sum_stmt = (
            select(func.coalesce(func.sum(GoalAllocation.value), Decimal("0")))
            .where(
                GoalAllocation.account_id == account_id,
                GoalAllocation.allocation_type == AllocationType.PERCENTAGE,
            )
        )
        current_sum = (await db.execute(sum_stmt)).scalar_one()
        if current_sum + value > Decimal("1.0"):
            raise ValueError(
                f"Invariant F-13: Percentage allocation sum for account {account_id} "
                f"would exceed 1.0 (current: {current_sum}, adding: {value})"
            )
    elif allocation_type == AllocationType.FIXED:
        if value < 0:
            raise ValueError("Fixed allocation value must be non-negative")

    # Invariant F-06: Ensure account_funds_goal edge exists; create if not
    edge_stmt = select(Edge).where(
        Edge.source_id == account_id,
        Edge.target_id == goal_id,
        Edge.relation_type == EdgeRelationType.ACCOUNT_FUNDS_GOAL,
    )
    existing_edge = (await db.execute(edge_stmt)).scalar_one_or_none()
    if existing_edge is None:
        edge = Edge(
            source_id=account_id,
            target_id=goal_id,
            relation_type=EdgeRelationType.ACCOUNT_FUNDS_GOAL,
            origin=EdgeOrigin.SYSTEM,
            state=EdgeState.ACTIVE,
            weight=1.0,
            metadata_={},
        )
        db.add(edge)

    allocation = GoalAllocation(
        goal_id=goal_id,
        account_id=account_id,
        allocation_type=allocation_type,
        value=value,
    )
    db.add(allocation)
    await db.flush()

    return allocation


async def get_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
) -> GoalAllocation | None:
    """Get an allocation by ID, enforcing ownership through the goal node."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.goal_id)
        .where(
            GoalAllocation.id == allocation_id,
            Node.owner_id == owner_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_allocations_for_goal(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_id: uuid.UUID,
) -> list[GoalAllocation]:
    """List all allocations for a goal, enforcing ownership."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.goal_id)
        .where(
            GoalAllocation.goal_id == goal_id,
            Node.owner_id == owner_id,
        )
        .order_by(GoalAllocation.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_allocations_for_account(
    db: AsyncSession,
    owner_id: uuid.UUID,
    account_id: uuid.UUID,
) -> list[GoalAllocation]:
    """List all allocations for an account, enforcing ownership."""
    stmt = (
        select(GoalAllocation)
        .join(Node, Node.id == GoalAllocation.account_id)
        .where(
            GoalAllocation.account_id == account_id,
            Node.owner_id == owner_id,
        )
        .order_by(GoalAllocation.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
    allocation_type: AllocationType | None = None,
    value: Decimal | None = None,
) -> GoalAllocation | None:
    """
    Update an allocation. Re-validates F-13 bounds on change.
    """
    alloc = await get_allocation(db, owner_id, allocation_id)
    if alloc is None:
        return None

    new_type = allocation_type or alloc.allocation_type
    new_value = value if value is not None else alloc.value

    if new_type == AllocationType.PERCENTAGE:
        if new_value < 0 or new_value > 1:
            raise ValueError("Percentage allocation value must be between 0.0 and 1.0")

        # Invariant F-13: Check sum excluding current allocation
        sum_stmt = (
            select(func.coalesce(func.sum(GoalAllocation.value), Decimal("0")))
            .where(
                GoalAllocation.account_id == alloc.account_id,
                GoalAllocation.allocation_type == AllocationType.PERCENTAGE,
                GoalAllocation.id != allocation_id,
            )
        )
        current_sum = (await db.execute(sum_stmt)).scalar_one()
        if current_sum + new_value > Decimal("1.0"):
            raise ValueError(
                f"Invariant F-13: Percentage allocation sum for account {alloc.account_id} "
                f"would exceed 1.0 (other: {current_sum}, new: {new_value})"
            )
    elif new_type == AllocationType.FIXED:
        if new_value < 0:
            raise ValueError("Fixed allocation value must be non-negative")

    if allocation_type is not None:
        alloc.allocation_type = allocation_type
    if value is not None:
        alloc.value = value

    alloc.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return alloc


async def delete_allocation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    allocation_id: uuid.UUID,
) -> bool:
    """Delete an allocation. Cleans up orphaned account_funds_goal edges."""
    alloc = await get_allocation(db, owner_id, allocation_id)
    if alloc is None:
        return False

    goal_id = alloc.goal_id
    account_id = alloc.account_id

    await db.delete(alloc)
    await db.flush()

    # Check if any other allocations remain for this account-goal pair
    remaining_stmt = select(func.count()).where(
        GoalAllocation.goal_id == goal_id,
        GoalAllocation.account_id == account_id,
    )
    remaining = (await db.execute(remaining_stmt)).scalar_one()

    # If no more allocations, remove the account_funds_goal edge
    if remaining == 0:
        edge_stmt = select(Edge).where(
            Edge.source_id == account_id,
            Edge.target_id == goal_id,
            Edge.relation_type == EdgeRelationType.ACCOUNT_FUNDS_GOAL,
        )
        edge = (await db.execute(edge_stmt)).scalar_one_or_none()
        if edge:
            await db.delete(edge)
            await db.flush()

    return True


# =============================================================================
# Goal Financial Extension
# =============================================================================


async def validate_goal_financial_fields(
    goal_type: GoalType,
    target_amount: Decimal | None,
    currency: str | None,
) -> None:
    """
    Invariant F-03: Financial goal field consistency.
    - financial: target_amount and currency must be non-null
    - general: all financial fields must be null
    Application layer enforcement (primary).
    """
    if goal_type == GoalType.FINANCIAL:
        if target_amount is None or currency is None:
            raise ValueError(
                "Invariant F-03: Financial goals require target_amount and currency to be non-null"
            )
    elif goal_type == GoalType.GENERAL:
        if target_amount is not None or currency is not None:
            raise ValueError(
                "Invariant F-03: General goals require target_amount and currency to be null"
            )


async def update_goal_financial(
    db: AsyncSession,
    owner_id: uuid.UUID,
    goal_node_id: uuid.UUID,
    goal_type: GoalType,
    target_amount: Decimal | None = None,
    currency: str | None = None,
) -> tuple[Node, GoalNode] | None:
    """
    Update goal financial fields with F-03 validation.
    Invariant F-03: Financial goals require target_amount + currency;
                    general goals require all financial fields null.
    """
    stmt = (
        select(Node, GoalNode)
        .join(GoalNode, GoalNode.node_id == Node.id)
        .where(Node.id == goal_node_id, Node.owner_id == owner_id)
    )
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None

    node, goal = row

    # Invariant F-03: Validate field consistency
    await validate_goal_financial_fields(goal_type, target_amount, currency)

    goal.goal_type = goal_type
    goal.target_amount = target_amount
    goal.currency = currency

    # If switching to general, clear current_amount too
    if goal_type == GoalType.GENERAL:
        goal.current_amount = None

    node.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return node, goal


# =============================================================================
# Balance Snapshot Service
# =============================================================================


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


# =============================================================================
# Audit Trail Service
# =============================================================================


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


# =============================================================================
# Transaction CRUD Service (Session F1-C)
# =============================================================================

# Valid status transitions: pending → posted → settled
VALID_STATUS_TRANSITIONS: dict[FinancialTransactionStatus, list[FinancialTransactionStatus]] = {
    FinancialTransactionStatus.PENDING: [FinancialTransactionStatus.POSTED],
    FinancialTransactionStatus.POSTED: [FinancialTransactionStatus.SETTLED],
    FinancialTransactionStatus.SETTLED: [],  # Terminal state
}


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
    """
    Create a financial transaction with audit trail.
    Invariant F-02: amount must be positive (application layer enforcement).
    Invariant F-11: creates audit history row on creation.
    """
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
    """
    Update a financial transaction.
    Invariant F-02: amount must be positive if provided.
    Invariant F-11: creates audit history row on update.
    Status lifecycle: pending → posted → settled.
    """
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
    """
    Void a transaction (soft delete). Sets is_voided = true.
    Invariant F-11: creates audit history row on void.
    Voided transactions excluded from balance calculations.
    """
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


# =============================================================================
# Transfer Pairing Service (Session F1-C)
# =============================================================================


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


# =============================================================================
# Balance Computation Service (Session F1-C)
# =============================================================================


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


# =============================================================================
# CSV Import Service (Session F1-C)
# =============================================================================


async def save_csv_mapping(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    column_mapping: dict[str, str],
    mapping_name: str = "default",
) -> CsvImportMapping:
    """
    Save a CSV column mapping for an account.
    Section 5.2: Save mapping per account for future imports.
    """
    # Verify account ownership
    acct_stmt = select(Node).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    acct = (await db.execute(acct_stmt)).scalar_one_or_none()
    if acct is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Check for existing mapping with same name for this account
    existing_stmt = select(CsvImportMapping).where(
        CsvImportMapping.account_id == account_id,
        CsvImportMapping.mapping_name == mapping_name,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is not None:
        existing.column_mapping = column_mapping
        existing.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    mapping = CsvImportMapping(
        user_id=user_id,
        account_id=account_id,
        mapping_name=mapping_name,
        column_mapping=column_mapping,
    )
    db.add(mapping)
    await db.flush()
    return mapping


async def get_csv_mappings(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> list[CsvImportMapping]:
    """Get all saved CSV column mappings for an account."""
    stmt = (
        select(CsvImportMapping)
        .where(
            CsvImportMapping.user_id == user_id,
            CsvImportMapping.account_id == account_id,
        )
        .order_by(CsvImportMapping.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _parse_csv_content(csv_content: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content string into headers and rows."""
    reader = csv.DictReader(io.StringIO(csv_content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def _map_csv_row_to_transaction(
    row: dict[str, str],
    column_mapping: dict[str, str],
    account_id: uuid.UUID,
    currency: str,
    row_number: int,
) -> tuple[dict | None, list[str]]:
    """
    Map a single CSV row to transaction fields using the column mapping.
    Returns (transaction_dict, errors).
    Invariant F-02: amount is always positive.
    """
    errors: list[str] = []
    tx_data: dict = {}

    # Required: amount
    amount_col = column_mapping.get("amount")
    if not amount_col or amount_col not in row:
        errors.append(f"Row {row_number}: Missing or unmapped 'amount' column")
        return None, errors

    try:
        raw_amount = row[amount_col].strip().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
        amount = Decimal(raw_amount)
        # Invariant F-02: amount always positive
        if amount == 0:
            errors.append(f"Row {row_number}: Amount is zero")
            return None, errors
        # If negative, treat as expense; if positive, treat as income
        if amount < 0:
            tx_data["amount"] = abs(amount)
            tx_data["transaction_type"] = FinancialTransactionType.EXPENSE
        else:
            tx_data["amount"] = amount
            tx_data["transaction_type"] = FinancialTransactionType.INCOME
    except (InvalidOperation, ValueError):
        errors.append(f"Row {row_number}: Invalid amount value '{row.get(amount_col, '')}'")
        return None, errors

    # Override transaction_type if mapped
    type_col = column_mapping.get("transaction_type")
    if type_col and type_col in row and row[type_col].strip():
        raw_type = row[type_col].strip().lower()
        try:
            tx_data["transaction_type"] = FinancialTransactionType(raw_type)
        except ValueError:
            # Try common aliases
            type_aliases = {
                "debit": FinancialTransactionType.EXPENSE,
                "credit": FinancialTransactionType.INCOME,
                "withdrawal": FinancialTransactionType.EXPENSE,
                "deposit": FinancialTransactionType.INCOME,
                "payment": FinancialTransactionType.EXPENSE,
            }
            if raw_type in type_aliases:
                tx_data["transaction_type"] = type_aliases[raw_type]

    # Required: date
    date_col = column_mapping.get("date")
    if date_col and date_col in row and row[date_col].strip():
        raw_date = row[date_col].strip()
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if parsed_date is None:
            errors.append(f"Row {row_number}: Cannot parse date '{raw_date}'")
            return None, errors
        tx_data["occurred_at"] = parsed_date
    else:
        tx_data["occurred_at"] = datetime.now(timezone.utc)

    # Optional fields
    desc_col = column_mapping.get("description")
    if desc_col and desc_col in row:
        tx_data["description"] = row[desc_col].strip() or None

    counterparty_col = column_mapping.get("counterparty")
    if counterparty_col and counterparty_col in row:
        tx_data["counterparty"] = row[counterparty_col].strip() or None

    ext_id_col = column_mapping.get("external_id")
    if ext_id_col and ext_id_col in row:
        tx_data["external_id"] = row[ext_id_col].strip() or None

    tx_data["account_id"] = account_id
    tx_data["currency"] = currency
    tx_data["source"] = TransactionSource.CSV_IMPORT
    tx_data["category_source"] = CategorySource.IMPORTED
    tx_data["status"] = FinancialTransactionStatus.POSTED

    return tx_data, errors


async def preview_csv_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    csv_content: str,
    column_mapping: dict[str, str],
) -> dict:
    """
    Preview CSV import: parse rows, detect duplicates, highlight errors.
    Section 5.2: Preview before commit with error/duplicate highlighting.
    Dedup via UNIQUE(account_id, external_id).
    """
    # Verify account ownership and get currency
    acct_result = await get_account(db, user_id, account_id)
    if acct_result is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")
    _, account_node = acct_result

    headers, rows = _parse_csv_content(csv_content)

    # Check for balance column
    balance_col = column_mapping.get("balance")
    has_balance_column = balance_col is not None and balance_col in headers

    preview_rows = []
    valid_count = 0
    error_count = 0
    duplicate_count = 0

    for i, row in enumerate(rows, start=1):
        tx_data, errors = _map_csv_row_to_transaction(
            row, column_mapping, account_id, account_node.currency, i
        )

        is_duplicate = False
        duplicate_tx_id = None

        if tx_data and not errors:
            # Check for duplicates via external_id
            ext_id = tx_data.get("external_id")
            if ext_id:
                dup_stmt = select(FinancialTransaction.id).where(
                    FinancialTransaction.account_id == account_id,
                    FinancialTransaction.external_id == ext_id,
                )
                dup_result = (await db.execute(dup_stmt)).scalar_one_or_none()
                if dup_result is not None:
                    is_duplicate = True
                    duplicate_tx_id = dup_result
                    duplicate_count += 1

        if errors:
            error_count += 1
        elif not is_duplicate:
            valid_count += 1

        preview_rows.append({
            "row_number": i,
            "data": dict(row),
            "transaction": tx_data,
            "errors": errors,
            "is_duplicate": is_duplicate,
            "duplicate_transaction_id": duplicate_tx_id,
        })

    return {
        "total_rows": len(rows),
        "valid_rows": valid_count,
        "error_rows": error_count,
        "duplicate_rows": duplicate_count,
        "rows": preview_rows,
        "detected_columns": headers,
        "has_balance_column": has_balance_column,
    }


async def execute_csv_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    csv_content: str,
    column_mapping: dict[str, str],
    save_mapping: bool = True,
    mapping_name: str = "default",
) -> dict:
    """
    Execute CSV import: bulk insert transactions, skip duplicates, auto-generate balance snapshots.
    Section 5.2: Bulk insert on confirm, dedup via UNIQUE(account_id, external_id).
    Invariant F-02: amounts always positive.
    Invariant F-11: audit trail for each imported transaction.
    """
    # Verify account ownership and get currency
    acct_result = await get_account(db, user_id, account_id)
    if acct_result is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")
    _, account_node = acct_result

    headers, rows = _parse_csv_content(csv_content)

    balance_col = column_mapping.get("balance")
    has_balance_column = balance_col is not None and balance_col in headers

    imported_ids: list[uuid.UUID] = []
    skipped_duplicates = 0
    error_count = 0
    balance_snapshots_created = 0

    for i, row in enumerate(rows, start=1):
        tx_data, errors = _map_csv_row_to_transaction(
            row, column_mapping, account_id, account_node.currency, i
        )

        if errors or tx_data is None:
            error_count += 1
            continue

        # Check for duplicate via external_id
        ext_id = tx_data.get("external_id")
        if ext_id:
            dup_stmt = select(FinancialTransaction.id).where(
                FinancialTransaction.account_id == account_id,
                FinancialTransaction.external_id == ext_id,
            )
            dup_result = (await db.execute(dup_stmt)).scalar_one_or_none()
            if dup_result is not None:
                skipped_duplicates += 1
                continue

        # Create the transaction
        tx = await create_transaction(
            db, user_id,
            account_id=tx_data["account_id"],
            transaction_type=tx_data["transaction_type"],
            amount=tx_data["amount"],
            currency=tx_data["currency"],
            status=tx_data.get("status", FinancialTransactionStatus.POSTED),
            counterparty=tx_data.get("counterparty"),
            description=tx_data.get("description"),
            occurred_at=tx_data.get("occurred_at"),
            source=TransactionSource.CSV_IMPORT,
            external_id=ext_id,
            category_source=CategorySource.IMPORTED,
        )
        imported_ids.append(tx.id)

        # Auto-generate balance_snapshot if balance column present
        if has_balance_column and balance_col in row and row[balance_col].strip():
            try:
                raw_balance = row[balance_col].strip().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
                balance_value = Decimal(raw_balance)
                snapshot_date = tx_data["occurred_at"].date() if isinstance(tx_data["occurred_at"], datetime) else tx_data["occurred_at"]

                await create_balance_snapshot(
                    db, user_id,
                    account_id=account_id,
                    balance=balance_value,
                    currency=account_node.currency,
                    snapshot_date=snapshot_date,
                    source=BalanceSnapshotSource.CSV_IMPORT,
                    is_reconciled=False,
                )
                balance_snapshots_created += 1
            except (InvalidOperation, ValueError):
                pass  # Skip invalid balance values silently

    # Save mapping for future imports if requested
    if save_mapping:
        await save_csv_mapping(db, user_id, account_id, column_mapping, mapping_name)

    return {
        "imported_count": len(imported_ids),
        "skipped_duplicates": skipped_duplicates,
        "error_count": error_count,
        "balance_snapshots_created": balance_snapshots_created,
        "transaction_ids": imported_ids,
    }


# =============================================================================
# Smart Defaults Service (Session F1-C)
# =============================================================================


async def get_manual_entry_defaults(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """
    Get smart defaults for manual transaction entry.
    Section 5.2: Most recently used account, date = today, status = posted.
    """
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
