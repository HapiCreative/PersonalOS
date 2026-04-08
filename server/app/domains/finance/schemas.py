"""
Pydantic schemas for finance domain (Finance Design Rev 3).
Covers: accounts, categories, allocations, balance snapshots, audit trail responses.
Invariants referenced: F-02, F-03, F-06, F-09, F-13.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from server.app.core.models.enums import (
    AccountType,
    AllocationType,
    BalanceSnapshotSource,
    CategorySource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    GoalType,
    TransactionChangeType,
    TransactionSource,
)


# =============================================================================
# Account Schemas
# =============================================================================


class AccountCreate(BaseModel):
    """Create an account node + companion."""
    title: str = Field(min_length=1, description="Account display name")
    summary: str | None = None
    account_type: AccountType
    institution: str | None = None
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217 currency code")
    account_number_masked: str | None = Field(default=None, max_length=4, description="Last 4 digits only")
    notes: str | None = None


class AccountUpdate(BaseModel):
    """Update account fields."""
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    account_type: AccountType | None = None
    institution: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    account_number_masked: str | None = Field(default=None, max_length=4)
    is_active: bool | None = None
    notes: str | None = None


class AccountResponse(BaseModel):
    """Account response with node + companion fields."""
    node_id: uuid.UUID
    title: str
    summary: str | None
    account_type: AccountType
    institution: str | None
    currency: str
    account_number_masked: str | None
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None

    model_config = {"from_attributes": True}


class AccountListResponse(BaseModel):
    items: list[AccountResponse]
    total: int


# =============================================================================
# Category Schemas
# =============================================================================


class CategoryCreate(BaseModel):
    """Create a financial category."""
    name: str = Field(min_length=1)
    parent_id: uuid.UUID | None = None
    icon: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    """Update a financial category."""
    name: str | None = Field(default=None, min_length=1)
    parent_id: uuid.UUID | None = None
    icon: str | None = None
    sort_order: int | None = None


class CategoryResponse(BaseModel):
    """Category response."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon: str | None
    is_system: bool
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryTreeResponse(BaseModel):
    """Category with children for hierarchy display."""
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon: str | None
    is_system: bool
    sort_order: int
    created_at: datetime
    children: list["CategoryTreeResponse"] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int


# =============================================================================
# Allocation Schemas
# =============================================================================


class AllocationCreate(BaseModel):
    """Create a goal allocation.
    Invariant F-13: percentage sum ≤ 1.0 per account across all goals.
    Invariant F-06: no shadow graph — allocations + edges only.
    """
    goal_id: uuid.UUID
    account_id: uuid.UUID
    allocation_type: AllocationType
    value: Decimal = Field(description="Percentage (0.0-1.0) or fixed amount (>= 0)")

    @field_validator("value")
    @classmethod
    def validate_value_non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("Allocation value must be non-negative")
        return v


class AllocationUpdate(BaseModel):
    """Update an allocation."""
    allocation_type: AllocationType | None = None
    value: Decimal | None = None

    @field_validator("value")
    @classmethod
    def validate_value_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("Allocation value must be non-negative")
        return v


class AllocationResponse(BaseModel):
    """Allocation response."""
    id: uuid.UUID
    goal_id: uuid.UUID
    account_id: uuid.UUID
    allocation_type: AllocationType
    value: Decimal
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AllocationListResponse(BaseModel):
    items: list[AllocationResponse]
    total: int


# =============================================================================
# Balance Snapshot Schemas
# =============================================================================


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


# =============================================================================
# Transaction History / Audit Trail Schemas
# =============================================================================


class TransactionHistoryResponse(BaseModel):
    """Audit trail entry for a financial transaction."""
    id: uuid.UUID
    transaction_id: uuid.UUID
    version: int
    snapshot: dict
    change_type: TransactionChangeType
    changed_by: uuid.UUID
    changed_at: datetime

    model_config = {"from_attributes": True}


class TransactionHistoryListResponse(BaseModel):
    items: list[TransactionHistoryResponse]
    total: int


# =============================================================================
# Goal Financial Extension Schemas
# =============================================================================


class GoalFinancialUpdate(BaseModel):
    """Update goal with financial fields.
    Invariant F-03: financial goals require target_amount + currency;
                    general goals require all financial fields null.
    """
    goal_type: GoalType
    target_amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("target_amount")
    @classmethod
    def validate_target_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("target_amount must be positive")
        return v
