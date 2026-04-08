"""Allocation and goal financial extension endpoints for the finance domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.allocations import (
    AllocationCreate,
    AllocationListResponse,
    AllocationResponse,
    AllocationUpdate,
    GoalFinancialUpdate,
)
from server.app.domains.finance.services.allocations import (
    create_allocation,
    delete_allocation,
    list_allocations_for_account,
    list_allocations_for_goal,
    update_allocation,
    update_goal_financial,
)

router = APIRouter()


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
