"""Obligation breakdown (sub-component) service functions.

F2.6: Versioned breakdown components for obligations.
Ref: Obligations Addendum Section 2, 7.

Invariant F-20: Breakdown amount model consistency.
Invariant F-21: One active breakdown version per normalized_name.
Invariant F-22: Deprecated breakdown has end date.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    BreakdownAmountModel,
    BreakdownComponentType,
    BreakdownStatus,
)
from server.app.domains.finance.models.obligations import ObligationBreakdown
from server.app.domains.finance.services.obligations import get_obligation


def _validate_breakdown_amount_model(
    amount_model: BreakdownAmountModel,
    expected_amount, percentage_value,
) -> None:
    """Invariant F-20: Breakdown amount model consistency (application layer)."""
    if amount_model == BreakdownAmountModel.PERCENTAGE:
        if percentage_value is None:
            raise ValueError(
                "Invariant F-20: percentage amount_model requires percentage_value"
            )
        if expected_amount is not None:
            raise ValueError(
                "Invariant F-20: percentage amount_model must not have expected_amount"
            )
    else:
        if percentage_value is not None:
            raise ValueError(
                "Invariant F-20: non-percentage amount_model must not have percentage_value"
            )


async def create_breakdown(
    db: AsyncSession,
    owner_id: uuid.UUID,
    obligation_id: uuid.UUID,
    *,
    name: str,
    normalized_name: str,
    component_type: BreakdownComponentType,
    amount_model: BreakdownAmountModel,
    effective_from: date,
    expected_amount=None,
    amount_range_low=None,
    amount_range_high=None,
    percentage_value=None,
    match_keywords: list[str] | None = None,
    sort_order: int = 0,
) -> ObligationBreakdown:
    """Create an obligation breakdown component.

    Invariant F-20: amount_model consistency validated.
    Invariant F-21: Checks no active version exists for same normalized_name.
    """
    # Verify obligation ownership
    pair = await get_obligation(db, owner_id, obligation_id, update_accessed=False)
    if pair is None:
        raise ValueError(f"Obligation {obligation_id} not found or not owned by user")

    # Invariant F-20
    _validate_breakdown_amount_model(amount_model, expected_amount, percentage_value)

    # Invariant F-21: Check for existing active version with same normalized_name
    existing_stmt = select(ObligationBreakdown).where(
        ObligationBreakdown.obligation_id == obligation_id,
        ObligationBreakdown.normalized_name == normalized_name,
        ObligationBreakdown.effective_to.is_(None),
    )
    if (await db.execute(existing_stmt)).scalar_one_or_none() is not None:
        raise ValueError(
            f"Invariant F-21: Active breakdown already exists for "
            f"normalized_name '{normalized_name}' on obligation {obligation_id}"
        )

    bd = ObligationBreakdown(
        obligation_id=obligation_id,
        name=name,
        normalized_name=normalized_name,
        component_type=component_type,
        amount_model=amount_model,
        expected_amount=expected_amount,
        amount_range_low=amount_range_low,
        amount_range_high=amount_range_high,
        percentage_value=percentage_value,
        match_keywords=match_keywords,
        effective_from=effective_from,
        sort_order=sort_order,
    )
    db.add(bd)
    await db.flush()
    return bd


async def list_breakdowns(
    db: AsyncSession,
    owner_id: uuid.UUID,
    obligation_id: uuid.UUID,
    *,
    include_deprecated: bool = False,
) -> list[ObligationBreakdown]:
    """List breakdowns for an obligation, enforcing ownership."""
    # Verify obligation ownership
    pair = await get_obligation(db, owner_id, obligation_id, update_accessed=False)
    if pair is None:
        raise ValueError(f"Obligation {obligation_id} not found or not owned by user")

    filters = [ObligationBreakdown.obligation_id == obligation_id]
    if not include_deprecated:
        filters.append(ObligationBreakdown.status == BreakdownStatus.ACTIVE)

    stmt = (
        select(ObligationBreakdown)
        .where(*filters)
        .order_by(ObligationBreakdown.sort_order, ObligationBreakdown.effective_from.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def version_breakdown(
    db: AsyncSession,
    owner_id: uuid.UUID,
    breakdown_id: uuid.UUID,
    *,
    name: str | None = None,
    component_type: BreakdownComponentType | None = None,
    amount_model: BreakdownAmountModel | None = None,
    expected_amount=...,
    amount_range_low=...,
    amount_range_high=...,
    percentage_value=...,
    match_keywords=...,
    sort_order: int | None = None,
) -> ObligationBreakdown:
    """Version a breakdown on rate change.

    Deprecates the old version (sets effective_to, status=deprecated) and
    creates a new version with effective_from=today.

    Invariant F-20: New version validated.
    Invariant F-21: Old version deprecated before new one created.
    Invariant F-22: Deprecated version gets effective_to set.
    """
    # Fetch old breakdown
    stmt = select(ObligationBreakdown).where(ObligationBreakdown.id == breakdown_id)
    old = (await db.execute(stmt)).scalar_one_or_none()
    if old is None:
        raise ValueError(f"Breakdown {breakdown_id} not found")

    # Verify obligation ownership
    pair = await get_obligation(db, owner_id, old.obligation_id, update_accessed=False)
    if pair is None:
        raise ValueError("Obligation not found or not owned by user")

    if old.status == BreakdownStatus.DEPRECATED:
        raise ValueError("Cannot version an already-deprecated breakdown")

    # Compute new values
    new_name = name if name is not None else old.name
    new_comp_type = component_type if component_type is not None else old.component_type
    new_model = amount_model if amount_model is not None else old.amount_model
    new_expected = expected_amount if expected_amount is not ... else old.expected_amount
    new_low = amount_range_low if amount_range_low is not ... else old.amount_range_low
    new_high = amount_range_high if amount_range_high is not ... else old.amount_range_high
    new_pct = percentage_value if percentage_value is not ... else old.percentage_value
    new_kw = match_keywords if match_keywords is not ... else old.match_keywords
    new_sort = sort_order if sort_order is not None else old.sort_order

    # Invariant F-20: Validate new version
    _validate_breakdown_amount_model(new_model, new_expected, new_pct)

    today = date.today()

    # Invariant F-22: Deprecate old version with effective_to
    old.effective_to = today
    old.status = BreakdownStatus.DEPRECATED
    old.updated_at = datetime.now(timezone.utc)

    # Create new version (Invariant F-21 satisfied: old now has effective_to set)
    new_bd = ObligationBreakdown(
        obligation_id=old.obligation_id,
        name=new_name,
        normalized_name=old.normalized_name,
        component_type=new_comp_type,
        amount_model=new_model,
        expected_amount=new_expected,
        amount_range_low=new_low,
        amount_range_high=new_high,
        percentage_value=new_pct,
        match_keywords=new_kw,
        effective_from=today,
        sort_order=new_sort,
    )
    db.add(new_bd)
    await db.flush()
    return new_bd


async def deprecate_breakdown(
    db: AsyncSession,
    owner_id: uuid.UUID,
    breakdown_id: uuid.UUID,
) -> ObligationBreakdown:
    """Deprecate a breakdown without creating a new version.

    Invariant F-22: deprecated status requires effective_to set.
    """
    stmt = select(ObligationBreakdown).where(ObligationBreakdown.id == breakdown_id)
    bd = (await db.execute(stmt)).scalar_one_or_none()
    if bd is None:
        raise ValueError(f"Breakdown {breakdown_id} not found")

    # Verify obligation ownership
    pair = await get_obligation(db, owner_id, bd.obligation_id, update_accessed=False)
    if pair is None:
        raise ValueError("Obligation not found or not owned by user")

    if bd.status == BreakdownStatus.DEPRECATED:
        raise ValueError("Breakdown is already deprecated")

    # Invariant F-22: deprecated -> effective_to must be set
    bd.status = BreakdownStatus.DEPRECATED
    bd.effective_to = date.today()
    bd.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return bd


async def get_breakdown_history(
    db: AsyncSession,
    owner_id: uuid.UUID,
    obligation_id: uuid.UUID,
    normalized_name: str,
) -> list[ObligationBreakdown]:
    """Get version history for a specific breakdown component."""
    # Verify obligation ownership
    pair = await get_obligation(db, owner_id, obligation_id, update_accessed=False)
    if pair is None:
        raise ValueError(f"Obligation {obligation_id} not found or not owned by user")

    stmt = (
        select(ObligationBreakdown)
        .where(
            ObligationBreakdown.obligation_id == obligation_id,
            ObligationBreakdown.normalized_name == normalized_name,
        )
        .order_by(ObligationBreakdown.effective_from.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
