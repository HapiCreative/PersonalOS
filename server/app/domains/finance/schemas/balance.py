"""Balance snapshot and computation schemas for the finance domain."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from server.app.core.models.enums import BalanceSnapshotSource


class BalanceSnapshotCreate(BaseModel):
    """Create a balance snapshot.
    Invariant F-09: reconciled snapshots are authoritative, never overridden.
    """
    account_id: uuid.UUID
    balance: Decimal
    currency: str = Field(min_length=3, max_length=3)
    snapshot_date: date
    source: BalanceSnapshotSource = BalanceSnapshotSource.MANUAL
    is_reconciled: bool = False


class BalanceSnapshotResponse(BaseModel):
    """Balance snapshot response."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    balance: Decimal
    currency: str
    snapshot_date: date
    source: BalanceSnapshotSource
    is_reconciled: bool
    reconciled_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceSnapshotListResponse(BaseModel):
    items: list[BalanceSnapshotResponse]
    total: int


class BalanceReconcile(BaseModel):
    """Mark a balance snapshot as reconciled.
    Invariant F-09: reconciled snapshot = source of truth.
    """
    is_reconciled: bool = True


class ComputedBalanceResponse(BaseModel):
    """Computed balance for an account.
    Invariant F-08: uses only posted/settled transactions.
    Invariant F-09: reconciled snapshot is authoritative.
    """
    account_id: uuid.UUID
    balance: Decimal
    currency: str
    as_of_date: date
    last_reconciled_snapshot: BalanceSnapshotResponse | None = None
    transactions_since_snapshot: int
    is_computed: bool  # True if computed from snapshot + transactions; False if direct reconciled snapshot
