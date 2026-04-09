"""Obligation breakdown (sub-component) endpoints for the finance domain.

F2.6: Versioned breakdown components. Create / list / version / deprecate / history.
Ref: Obligations Addendum Section 2, 7.

Invariants enforced via service layer:
- F-20: breakdown amount model consistency
- F-21: one active breakdown version per normalized_name
- F-22: deprecated breakdown has end date
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.obligations import (
    BreakdownCreate,
    BreakdownListResponse,
    BreakdownResponse,
    BreakdownUpdate,
)
from server.app.domains.finance.services.obligation_breakdowns import (
    create_breakdown,
    deprecate_breakdown,
    get_breakdown_history,
    list_breakdowns,
    version_breakdown,
)

router = APIRouter()


@router.post(
    "/obligations/{obligation_id}/breakdowns",
    response_model=BreakdownResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_breakdown_endpoint(
    obligation_id: uuid.UUID,
    body: BreakdownCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a breakdown component.

    Invariant F-20: amount model consistency validated.
    Invariant F-21: no duplicate active version for same normalized_name.
    """
    try:
        bd = await create_breakdown(
            db, user.id, obligation_id,
            name=body.name,
            normalized_name=body.normalized_name,
            component_type=body.component_type,
            amount_model=body.amount_model,
            effective_from=body.effective_from,
            expected_amount=body.expected_amount,
            amount_range_low=body.amount_range_low,
            amount_range_high=body.amount_range_high,
            percentage_value=body.percentage_value,
            match_keywords=body.match_keywords,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return BreakdownResponse.model_validate(bd)


@router.get(
    "/obligations/{obligation_id}/breakdowns",
    response_model=BreakdownListResponse,
)
async def list_breakdowns_endpoint(
    obligation_id: uuid.UUID,
    include_deprecated: bool = Query(
        default=False, description="Include deprecated breakdown versions",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List breakdown components for an obligation."""
    try:
        items = await list_breakdowns(
            db, user.id, obligation_id, include_deprecated=include_deprecated,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return BreakdownListResponse(
        items=[BreakdownResponse.model_validate(bd) for bd in items],
        total=len(items),
    )


@router.get(
    "/obligations/{obligation_id}/breakdowns/history/{normalized_name}",
    response_model=BreakdownListResponse,
)
async def get_breakdown_history_endpoint(
    obligation_id: uuid.UUID,
    normalized_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the version history for a specific breakdown component."""
    try:
        items = await get_breakdown_history(db, user.id, obligation_id, normalized_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return BreakdownListResponse(
        items=[BreakdownResponse.model_validate(bd) for bd in items],
        total=len(items),
    )


@router.put(
    "/obligations/breakdowns/{breakdown_id}",
    response_model=BreakdownResponse,
)
async def version_breakdown_endpoint(
    breakdown_id: uuid.UUID,
    body: BreakdownUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Version a breakdown on rate change.

    Deprecates old version and creates a new version with today's effective_from.
    Invariants F-20, F-21, F-22 enforced by service layer.
    """
    try:
        new_bd = await version_breakdown(
            db, user.id, breakdown_id,
            name=body.name,
            component_type=body.component_type,
            amount_model=body.amount_model,
            expected_amount=body.expected_amount if body.expected_amount is not None else ...,
            amount_range_low=body.amount_range_low if body.amount_range_low is not None else ...,
            amount_range_high=body.amount_range_high if body.amount_range_high is not None else ...,
            percentage_value=body.percentage_value if body.percentage_value is not None else ...,
            match_keywords=body.match_keywords if body.match_keywords is not None else ...,
            sort_order=body.sort_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return BreakdownResponse.model_validate(new_bd)


@router.post(
    "/obligations/breakdowns/{breakdown_id}/deprecate",
    response_model=BreakdownResponse,
)
async def deprecate_breakdown_endpoint(
    breakdown_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deprecate a breakdown without creating a new version.

    Invariant F-22: sets effective_to to today.
    """
    try:
        bd = await deprecate_breakdown(db, user.id, breakdown_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return BreakdownResponse.model_validate(bd)
