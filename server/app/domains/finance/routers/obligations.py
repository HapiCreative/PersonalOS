"""Obligation endpoints for the finance domain.

F2.6: Obligation CRUD + lifecycle (create, list, get, update, cancel, pause, resume).
Ref: Obligations Addendum Sections 1, 2, 5.1, 8.1.

Invariants enforced via service layer:
- F-17: amount model consistency
- F-18: status lifecycle
- F-19: next_expected_date cached derived
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.enums import ObligationStatus, ObligationType
from server.app.core.models.user import User
from server.app.domains.finance.schemas.obligations import (
    ObligationCreate,
    ObligationListResponse,
    ObligationResponse,
    ObligationUpdate,
)
from server.app.domains.finance.services.obligations import (
    cancel_obligation,
    create_obligation,
    get_obligation,
    list_obligations,
    pause_obligation,
    resume_obligation,
    update_obligation,
)

router = APIRouter()


def obligation_to_response(node, obligation) -> ObligationResponse:
    """Map (Node, ObligationNode) to response schema.

    Exported for use by related routers (e.g. obligation_breakdowns).
    """
    return ObligationResponse(
        node_id=node.id,
        title=node.title,
        summary=node.summary,
        obligation_type=obligation.obligation_type,
        recurrence_rule=obligation.recurrence_rule,
        amount_model=obligation.amount_model,
        expected_amount=obligation.expected_amount,
        amount_range_low=obligation.amount_range_low,
        amount_range_high=obligation.amount_range_high,
        currency=obligation.currency,
        account_id=obligation.account_id,
        counterparty_entity_id=obligation.counterparty_entity_id,
        category_id=obligation.category_id,
        billing_anchor=obligation.billing_anchor,
        next_expected_date=obligation.next_expected_date,
        status=obligation.status,
        autopay=obligation.autopay,
        origin=obligation.origin,
        confidence=obligation.confidence,
        started_at=obligation.started_at,
        ended_at=obligation.ended_at,
        cancellation_url=obligation.cancellation_url,
        notes=obligation.notes,
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


@router.post(
    "/obligations",
    response_model=ObligationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_obligation_endpoint(
    body: ObligationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an obligation (node + obligation_nodes companion).

    Invariant F-17: amount_model consistency validated.
    Invariant F-19: next_expected_date cached on creation.
    """
    try:
        node, obligation = await create_obligation(
            db, user.id,
            title=body.title,
            summary=body.summary,
            obligation_type=body.obligation_type,
            recurrence_rule=body.recurrence_rule,
            amount_model=body.amount_model,
            expected_amount=body.expected_amount,
            amount_range_low=body.amount_range_low,
            amount_range_high=body.amount_range_high,
            currency=body.currency,
            account_id=body.account_id,
            category_id=body.category_id,
            billing_anchor=body.billing_anchor,
            autopay=body.autopay,
            origin=body.origin,
            confidence=body.confidence,
            started_at=body.started_at,
            cancellation_url=body.cancellation_url,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return obligation_to_response(node, obligation)


@router.get("/obligations", response_model=ObligationListResponse)
async def list_obligations_endpoint(
    status_filter: ObligationStatus | None = Query(
        default=None, alias="status", description="Filter by status",
    ),
    obligation_type: ObligationType | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List obligations with optional filters."""
    items, total = await list_obligations(
        db, user.id,
        status=status_filter,
        obligation_type=obligation_type,
        account_id=account_id,
        limit=limit,
        offset=offset,
    )
    return ObligationListResponse(
        items=[obligation_to_response(n, o) for n, o in items],
        total=total,
    )


@router.get("/obligations/{node_id}", response_model=ObligationResponse)
async def get_obligation_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single obligation by node ID."""
    pair = await get_obligation(db, user.id, node_id)
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found",
        )
    return obligation_to_response(*pair)


@router.put("/obligations/{node_id}", response_model=ObligationResponse)
async def update_obligation_endpoint(
    node_id: uuid.UUID,
    body: ObligationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update obligation fields.

    Invariant F-17 re-validated on amount_model changes.
    Invariant F-19 re-computed on recurrence_rule changes.
    """
    try:
        pair = await update_obligation(
            db, user.id, node_id,
            title=body.title,
            summary=body.summary if body.summary is not None else ...,
            obligation_type=body.obligation_type,
            recurrence_rule=body.recurrence_rule,
            amount_model=body.amount_model,
            expected_amount=body.expected_amount if body.expected_amount is not None else ...,
            amount_range_low=body.amount_range_low if body.amount_range_low is not None else ...,
            amount_range_high=body.amount_range_high if body.amount_range_high is not None else ...,
            currency=body.currency,
            account_id=body.account_id,
            category_id=body.category_id if body.category_id is not None else ...,
            billing_anchor=body.billing_anchor if body.billing_anchor is not None else ...,
            autopay=body.autopay,
            cancellation_url=body.cancellation_url if body.cancellation_url is not None else ...,
            notes=body.notes if body.notes is not None else ...,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found",
        )
    return obligation_to_response(*pair)


@router.post("/obligations/{node_id}/cancel", response_model=ObligationResponse)
async def cancel_obligation_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an obligation. Invariant F-18: sets ended_at."""
    try:
        pair = await cancel_obligation(db, user.id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found",
        )
    return obligation_to_response(*pair)


@router.post("/obligations/{node_id}/pause", response_model=ObligationResponse)
async def pause_obligation_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Pause an active obligation."""
    try:
        pair = await pause_obligation(db, user.id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found",
        )
    return obligation_to_response(*pair)


@router.post("/obligations/{node_id}/resume", response_model=ObligationResponse)
async def resume_obligation_endpoint(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused obligation. Invariant F-19: recomputes next_expected_date."""
    try:
        pair = await resume_obligation(db, user.id, node_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if pair is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obligation not found",
        )
    return obligation_to_response(*pair)
