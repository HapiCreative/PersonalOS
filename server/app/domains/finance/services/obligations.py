"""Obligation CRUD and lifecycle service functions.

F2.6: Core obligation entities with companion table pattern.
Ref: Obligations Addendum Sections 1, 2, 5.1, 8.1.

Invariant F-17: Obligation amount model consistency.
Invariant F-18: Obligation status lifecycle.
Invariant F-19: next_expected_date is CACHED DERIVED (S-01).
"""

import uuid
from datetime import date, datetime, timezone

from dateutil.rrule import rrulestr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    AmountModel,
    NodeType,
    ObligationOrigin,
    ObligationStatus,
    ObligationType,
)
from server.app.core.models.node import Node
from server.app.domains.finance.models.obligations import ObligationNode


# ---------------------------------------------------------------------------
# Helpers (shared with obligation_breakdowns via internal import)
# ---------------------------------------------------------------------------


def compute_next_expected_date(
    recurrence_rule: str,
    after_date: date | None = None,
) -> date | None:
    """Invariant F-19: Compute next_expected_date from recurrence_rule.

    Uses dateutil rrulestr to parse RRULE strings. Falls back to None if
    the rule cannot be parsed or yields no future dates.

    Phase 3 dependency: once obligation_events exist, after_date should be
    derived from the last obligation_event's expected_for_date.
    """
    if after_date is None:
        after_date = date.today()

    try:
        rule = rrulestr(recurrence_rule, ignoretz=True)
        dt_after = datetime(after_date.year, after_date.month, after_date.day)
        next_dt = rule.after(dt_after, inc=False)
        if next_dt is not None:
            return next_dt.date()
    except (ValueError, TypeError):
        pass
    return None


async def _verify_account_ownership(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID,
) -> None:
    """Raise ValueError if account node not found or not owned by user."""
    stmt = select(Node).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")


def _validate_amount_model(
    amount_model: AmountModel,
    expected_amount, amount_range_low, amount_range_high,
) -> None:
    """Invariant F-17: Amount model consistency (application layer)."""
    if amount_model == AmountModel.FIXED:
        if expected_amount is None:
            raise ValueError("Invariant F-17: fixed amount_model requires expected_amount")
        if amount_range_low is not None or amount_range_high is not None:
            raise ValueError("Invariant F-17: fixed amount_model must not have range fields")
    elif amount_model in (AmountModel.VARIABLE, AmountModel.SEASONAL):
        if amount_range_low is None or amount_range_high is None:
            raise ValueError(
                "Invariant F-17: variable/seasonal amount_model requires range fields"
            )


# ---------------------------------------------------------------------------
# Obligation CRUD
# ---------------------------------------------------------------------------


async def create_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    title: str,
    obligation_type: ObligationType,
    recurrence_rule: str,
    amount_model: AmountModel,
    currency: str,
    account_id: uuid.UUID,
    summary: str | None = None,
    expected_amount=None,
    amount_range_low=None,
    amount_range_high=None,
    category_id: uuid.UUID | None = None,
    billing_anchor: int | None = None,
    autopay: bool = False,
    origin: ObligationOrigin = ObligationOrigin.MANUAL,
    confidence: float | None = None,
    started_at: date | None = None,
    cancellation_url: str | None = None,
    notes: str | None = None,
) -> tuple[Node, ObligationNode]:
    """Create an obligation (Core node + obligation_nodes companion).

    Invariant F-17: amount_model consistency validated.
    Invariant F-19: next_expected_date computed and cached.
    """
    # Invariant F-17
    _validate_amount_model(amount_model, expected_amount, amount_range_low, amount_range_high)

    await _verify_account_ownership(db, owner_id, account_id)

    # Create the graph node
    node = Node(
        type=NodeType.OBLIGATION,
        owner_id=owner_id,
        title=title,
        summary=summary,
    )
    db.add(node)
    await db.flush()

    # Invariant F-19: Compute initial next_expected_date
    base_date = started_at if started_at else date.today()
    next_date = compute_next_expected_date(recurrence_rule, after_date=base_date)

    obligation = ObligationNode(
        node_id=node.id,
        obligation_type=obligation_type,
        recurrence_rule=recurrence_rule,
        amount_model=amount_model,
        expected_amount=expected_amount,
        amount_range_low=amount_range_low,
        amount_range_high=amount_range_high,
        currency=currency,
        account_id=account_id,
        category_id=category_id,
        billing_anchor=billing_anchor,
        next_expected_date=next_date,
        status=ObligationStatus.ACTIVE,
        autopay=autopay,
        origin=origin,
        confidence=confidence,
        started_at=started_at,
        cancellation_url=cancellation_url,
        notes=notes,
    )
    db.add(obligation)
    await db.flush()

    return node, obligation


async def get_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    update_accessed: bool = True,
) -> tuple[Node, ObligationNode] | None:
    """Get an obligation by node ID, enforcing ownership."""
    stmt = (
        select(Node, ObligationNode)
        .join(ObligationNode, ObligationNode.node_id == Node.id)
        .where(Node.id == node_id, Node.owner_id == owner_id)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None

    node, obligation = row
    if update_accessed:
        node.last_accessed_at = datetime.now(timezone.utc)
        await db.flush()
    return node, obligation


async def list_obligations(
    db: AsyncSession,
    owner_id: uuid.UUID,
    *,
    status: ObligationStatus | None = None,
    obligation_type: ObligationType | None = None,
    account_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[tuple[Node, ObligationNode]], int]:
    """List obligations with optional filters, enforcing ownership."""
    filters = [Node.owner_id == owner_id, Node.type == NodeType.OBLIGATION]
    if status is not None:
        filters.append(ObligationNode.status == status)
    if obligation_type is not None:
        filters.append(ObligationNode.obligation_type == obligation_type)
    if account_id is not None:
        filters.append(ObligationNode.account_id == account_id)

    count_stmt = (
        select(func.count())
        .select_from(Node)
        .join(ObligationNode, ObligationNode.node_id == Node.id)
        .where(*filters)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        select(Node, ObligationNode)
        .join(ObligationNode, ObligationNode.node_id == Node.id)
        .where(*filters)
        .order_by(ObligationNode.next_expected_date.asc().nullslast(), Node.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await db.execute(stmt)).all())
    return items, total


async def update_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
    *,
    title: str | None = None,
    summary: str | None = ...,  # type: ignore[assignment]
    obligation_type: ObligationType | None = None,
    recurrence_rule: str | None = None,
    amount_model: AmountModel | None = None,
    expected_amount=...,
    amount_range_low=...,
    amount_range_high=...,
    currency: str | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = ...,  # type: ignore[assignment]
    billing_anchor: int | None = ...,  # type: ignore[assignment]
    autopay: bool | None = None,
    cancellation_url: str | None = ...,  # type: ignore[assignment]
    notes: str | None = ...,  # type: ignore[assignment]
) -> tuple[Node, ObligationNode] | None:
    """Update obligation fields, enforcing ownership.

    Invariant F-17: If amount_model changes, revalidate consistency.
    Invariant F-19: If recurrence_rule changes, recompute next_expected_date.
    """
    pair = await get_obligation(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, obligation = pair

    # Node fields
    if title is not None:
        node.title = title
    if summary is not ...:
        node.summary = summary

    # Obligation companion fields
    if obligation_type is not None:
        obligation.obligation_type = obligation_type
    if currency is not None:
        obligation.currency = currency
    if account_id is not None:
        await _verify_account_ownership(db, owner_id, account_id)
        obligation.account_id = account_id
    if category_id is not ...:
        obligation.category_id = category_id
    if billing_anchor is not ...:
        obligation.billing_anchor = billing_anchor
    if autopay is not None:
        obligation.autopay = autopay
    if cancellation_url is not ...:
        obligation.cancellation_url = cancellation_url
    if notes is not ...:
        obligation.notes = notes

    # Amount model fields — validate consistency if any change
    new_model = amount_model if amount_model is not None else obligation.amount_model
    new_expected = expected_amount if expected_amount is not ... else obligation.expected_amount
    new_low = amount_range_low if amount_range_low is not ... else obligation.amount_range_low
    new_high = amount_range_high if amount_range_high is not ... else obligation.amount_range_high

    # Invariant F-17: Validate new combination
    _validate_amount_model(new_model, new_expected, new_low, new_high)

    obligation.amount_model = new_model
    obligation.expected_amount = new_expected
    obligation.amount_range_low = new_low
    obligation.amount_range_high = new_high

    # Invariant F-19: Recompute next_expected_date if rule changed
    if recurrence_rule is not None:
        obligation.recurrence_rule = recurrence_rule
        base = obligation.started_at if obligation.started_at else date.today()
        obligation.next_expected_date = compute_next_expected_date(
            recurrence_rule, after_date=base,
        )

    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, obligation


async def cancel_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, ObligationNode] | None:
    """Cancel an obligation.

    Invariant F-18: cancelled requires ended_at set.
    """
    pair = await get_obligation(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, obligation = pair
    if obligation.status == ObligationStatus.CANCELLED:
        raise ValueError("Obligation is already cancelled")

    # Invariant F-18: cancelled -> ended_at must be set
    obligation.status = ObligationStatus.CANCELLED
    obligation.ended_at = date.today()
    obligation.next_expected_date = None
    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, obligation


async def pause_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, ObligationNode] | None:
    """Pause an active obligation.

    Invariant F-18: paused allows ended_at in either state.
    """
    pair = await get_obligation(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, obligation = pair
    if obligation.status != ObligationStatus.ACTIVE:
        raise ValueError(
            f"Cannot pause obligation with status '{obligation.status.value}'; must be active"
        )

    obligation.status = ObligationStatus.PAUSED
    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, obligation


async def resume_obligation(
    db: AsyncSession,
    owner_id: uuid.UUID,
    node_id: uuid.UUID,
) -> tuple[Node, ObligationNode] | None:
    """Resume a paused obligation.

    Invariant F-18: active requires ended_at null.
    Invariant F-19: Recompute next_expected_date on resume.
    """
    pair = await get_obligation(db, owner_id, node_id, update_accessed=False)
    if pair is None:
        return None

    node, obligation = pair
    if obligation.status != ObligationStatus.PAUSED:
        raise ValueError(
            f"Cannot resume obligation with status '{obligation.status.value}'; must be paused"
        )

    # Invariant F-18: active -> ended_at must be null
    obligation.status = ObligationStatus.ACTIVE
    obligation.ended_at = None

    # Invariant F-19: Recompute next_expected_date
    obligation.next_expected_date = compute_next_expected_date(
        obligation.recurrence_rule,
        after_date=date.today(),
    )
    node.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return node, obligation
