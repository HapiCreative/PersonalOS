"""
Finance domain router (Section 8.3, Finance Design Rev 3).
Endpoints for accounts, categories, allocations, balance snapshots, audit trail,
and goal financial extension.

Layer: Core (read/write)
All endpoints enforce ownership (v6 Section 8.2 — every query filters by owner scope).

Invariants enforced at API level:
- F-01: Transactions never become nodes
- F-03: Goal financial field consistency
- F-06: No shadow graph
- F-09: Reconciled snapshots authoritative
- F-12: Category deletion blocked by referential integrity
- F-13: Allocation bounds
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.core.models.enums import BalanceSnapshotSource
from server.app.domains.finance.schemas import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
    AllocationCreate,
    AllocationListResponse,
    AllocationResponse,
    AllocationUpdate,
    BalanceSnapshotCreate,
    BalanceSnapshotListResponse,
    BalanceSnapshotResponse,
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryTreeResponse,
    CategoryUpdate,
    GoalFinancialUpdate,
    TransactionHistoryListResponse,
    TransactionHistoryResponse,
)
from server.app.domains.finance.service import (
    create_account,
    create_allocation,
    create_balance_snapshot,
    create_category,
    deactivate_account,
    delete_allocation,
    delete_category,
    get_account,
    get_allocation,
    get_transaction_history,
    list_accounts,
    list_allocations_for_account,
    list_allocations_for_goal,
    list_balance_snapshots,
    list_categories,
    list_categories_tree,
    seed_categories_for_user,
    update_account,
    update_allocation,
    update_category,
    update_goal_financial,
)

router = APIRouter(prefix="/api/finance", tags=["finance"])


# =============================================================================
# Account Endpoints
# =============================================================================


def _account_to_response(node, account) -> AccountResponse:
    return AccountResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        account_type=account.account_type,
        institution=account.institution,
        currency=account.currency,
        account_number_masked=account.account_number_masked,
        is_active=account.is_active,
        notes=account.notes,
        created_at=node.created_at,
        updated_at=node.updated_at,
        archived_at=node.archived_at,
    )


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account_endpoint(
    body: AccountCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new financial account (node + companion)."""
    node, account = await create_account(
        db, user.id,
        title=body.title,
        account_type=body.account_type,
        currency=body.currency,
        summary=body.summary,
        institution=body.institution,
        account_number_masked=body.account_number_masked,
        notes=body.notes,
    )
    return _account_to_response(node, account)


@router.get("/accounts", response_model=AccountListResponse)
async def list_accounts_endpoint(
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List accounts with optional active/inactive filter."""
    items, total = await list_accounts(db, user.id, is_active, limit, offset)
    return AccountListResponse(
        items=[_account_to_response(n, a) for n, a in items],
        total=total,
    )


@router.get("/accounts/{node_id}", response_model=AccountResponse)
async def get_account_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single account by node ID."""
    pair = await get_account(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _account_to_response(*pair)


@router.put("/accounts/{node_id}", response_model=AccountResponse)
async def update_account_endpoint(
    node_id: uuid.UUID,
    body: AccountUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update account fields."""
    pair = await update_account(
        db, user.id, node_id,
        title=body.title,
        summary=body.summary if body.summary is not None else ...,
        account_type=body.account_type,
        institution=body.institution if body.institution is not None else ...,
        currency=body.currency,
        account_number_masked=body.account_number_masked if body.account_number_masked is not None else ...,
        is_active=body.is_active,
        notes=body.notes if body.notes is not None else ...,
    )
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _account_to_response(*pair)


@router.post("/accounts/{node_id}/deactivate", response_model=AccountResponse)
async def deactivate_account_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft deactivate an account (set is_active = false)."""
    pair = await deactivate_account(db, user.id, node_id)
    if pair is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _account_to_response(*pair)


# =============================================================================
# Category Endpoints
# =============================================================================


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category_endpoint(
    body: CategoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a user financial category."""
    try:
        cat = await create_category(
            db, user.id,
            name=body.name,
            parent_id=body.parent_id,
            icon=body.icon,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return CategoryResponse.model_validate(cat)


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories_endpoint(
    parent_id: uuid.UUID | None = Query(default=..., description="Filter by parent (null for top-level)"),
    limit: int = Query(default=100, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List categories with optional parent filter."""
    items, total = await list_categories(db, user.id, parent_id=parent_id, limit=limit, offset=offset)
    return CategoryListResponse(
        items=[CategoryResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get("/categories/tree", response_model=list[CategoryTreeResponse])
async def list_categories_tree_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all categories as a hierarchical tree."""
    all_cats = await list_categories_tree(db, user.id)

    # Build tree from flat list
    cat_map: dict[uuid.UUID, CategoryTreeResponse] = {}
    roots: list[CategoryTreeResponse] = []

    for c in all_cats:
        tree_item = CategoryTreeResponse(
            id=c.id,
            user_id=c.user_id,
            name=c.name,
            parent_id=c.parent_id,
            icon=c.icon,
            is_system=c.is_system,
            sort_order=c.sort_order,
            created_at=c.created_at,
            children=[],
        )
        cat_map[c.id] = tree_item

    for c in all_cats:
        tree_item = cat_map[c.id]
        if c.parent_id and c.parent_id in cat_map:
            cat_map[c.parent_id].children.append(tree_item)
        else:
            roots.append(tree_item)

    return roots


@router.get("/categories/{category_id}", response_model=CategoryResponse)
async def get_category_endpoint(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single category."""
    from server.app.domains.finance.service import get_category
    cat = await get_category(db, user.id, category_id)
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category_endpoint(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a category."""
    try:
        cat = await update_category(
            db, user.id, category_id,
            name=body.name,
            parent_id=body.parent_id if body.parent_id is not None else ...,
            icon=body.icon if body.icon is not None else ...,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if cat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return CategoryResponse.model_validate(cat)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_endpoint(
    category_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a category.
    Invariant F-12: Blocked if transactions reference it.
    """
    try:
        success = await delete_category(db, user.id, category_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")


@router.post("/categories/seed", response_model=list[CategoryResponse])
async def seed_categories_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seed system default categories for the current user. Idempotent."""
    cats = await seed_categories_for_user(db, user.id)
    return [CategoryResponse.model_validate(c) for c in cats]


# =============================================================================
# Allocation Endpoints
# =============================================================================


@router.post("/allocations", response_model=AllocationResponse, status_code=status.HTTP_201_CREATED)
async def create_allocation_endpoint(
    body: AllocationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a goal allocation.
    Invariant F-13: percentage sum ≤ 1.0 per account.
    Invariant F-06: ensures account_funds_goal edge exists.
    """
    try:
        alloc = await create_allocation(
            db, user.id,
            goal_id=body.goal_id,
            account_id=body.account_id,
            allocation_type=body.allocation_type,
            value=body.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return AllocationResponse.model_validate(alloc)


@router.get("/allocations/goal/{goal_id}", response_model=AllocationListResponse)
async def list_allocations_for_goal_endpoint(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all allocations for a goal."""
    items = await list_allocations_for_goal(db, user.id, goal_id)
    return AllocationListResponse(
        items=[AllocationResponse.model_validate(a) for a in items],
        total=len(items),
    )


@router.get("/allocations/account/{account_id}", response_model=AllocationListResponse)
async def list_allocations_for_account_endpoint(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all allocations for an account."""
    items = await list_allocations_for_account(db, user.id, account_id)
    return AllocationListResponse(
        items=[AllocationResponse.model_validate(a) for a in items],
        total=len(items),
    )


@router.put("/allocations/{allocation_id}", response_model=AllocationResponse)
async def update_allocation_endpoint(
    allocation_id: uuid.UUID,
    body: AllocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an allocation. Re-validates F-13 bounds."""
    try:
        alloc = await update_allocation(
            db, user.id, allocation_id,
            allocation_type=body.allocation_type,
            value=body.value,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if alloc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return AllocationResponse.model_validate(alloc)


@router.delete("/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allocation_endpoint(
    allocation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an allocation. Cleans up orphaned account_funds_goal edges."""
    success = await delete_allocation(db, user.id, allocation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")


# =============================================================================
# Balance Snapshot Endpoints
# =============================================================================


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


# =============================================================================
# Goal Financial Extension Endpoints
# =============================================================================


@router.put("/goals/{node_id}/financial", response_model=dict)
async def update_goal_financial_endpoint(
    node_id: uuid.UUID,
    body: GoalFinancialUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update goal financial fields.
    Invariant F-03: financial goals require target_amount + currency;
                    general goals require all financial fields null.
    """
    try:
        result = await update_goal_financial(
            db, user.id, node_id,
            goal_type=body.goal_type,
            target_amount=body.target_amount,
            currency=body.currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    node, goal = result
    return {
        "node_id": str(node.id),
        "goal_type": goal.goal_type.value,
        "target_amount": str(goal.target_amount) if goal.target_amount else None,
        "current_amount": str(goal.current_amount) if goal.current_amount else None,
        "currency": goal.currency,
    }


# =============================================================================
# Audit Trail Endpoints
# =============================================================================


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
