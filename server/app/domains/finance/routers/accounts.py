"""Account endpoints for the finance domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.accounts import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
)
from server.app.domains.finance.services.accounts import (
    create_account,
    deactivate_account,
    get_account,
    list_accounts,
    update_account,
)

router = APIRouter()


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
