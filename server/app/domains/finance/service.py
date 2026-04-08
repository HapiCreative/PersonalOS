"""
Finance domain service (Finance Design Rev 3, Sections 2.1–2.6, 3.2, 3.6).
Backend Core Services for accounts, categories, allocations, balance snapshots, audit trail.

Invariants enforced:
- F-01: Transactions never become nodes (architectural constraint)
- F-03: Financial goal field consistency (application layer, primary)
- F-06: No shadow graph — relationships are edges + allocations only
- F-09: Reconciled snapshots are authoritative, never overridden by computed
- F-11: Every financial_transaction mutation → history row (application layer)
- F-12: Category deletion blocked if transactions reference it (DB RESTRICT + app check)
- F-13: Percentage allocation sum ≤ 1.0 per account across all goals (application layer, primary)
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.edge import Edge
from server.app.core.models.enums import (
    AccountType,
    AllocationType,
    BalanceSnapshotSource,
    EdgeRelationType,
    EdgeOrigin,
    EdgeState,
    GoalType,
    NodeType,
    TransactionChangeType,
)
from server.app.core.models.node import (
    AccountNode,
    BalanceSnapshot,
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
