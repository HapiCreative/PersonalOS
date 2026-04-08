"""
Pydantic schemas for finance domain (Finance Design Rev 3).
Covers: accounts, categories, allocations, balance snapshots, audit trail,
transactions, transfers, CSV import, and balance computation responses.
Invariants referenced: F-02, F-03, F-05, F-06, F-08, F-09, F-11, F-13.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

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


# =============================================================================
# Transaction Schemas (Session F1-C)
# =============================================================================


class TransactionCreate(BaseModel):
    """Create a financial transaction.
    Invariant F-02: amount must be positive; direction encoded in transaction_type.
    """
    account_id: uuid.UUID
    transaction_type: FinancialTransactionType
    amount: Decimal = Field(gt=0, description="Always positive (F-02)")
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    category_source: CategorySource = CategorySource.MANUAL
    counterparty: str | None = None
    description: str | None = None
    occurred_at: datetime | None = None  # Defaults to now if not provided
    posted_at: datetime | None = None
    source: TransactionSource = TransactionSource.MANUAL
    external_id: str | None = None
    tags: list[str] | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: Decimal) -> Decimal:
        # Invariant F-02: amount always positive
        if v <= 0:
            raise ValueError("Invariant F-02: amount must be positive")
        return v


class TransactionUpdate(BaseModel):
    """Update a financial transaction.
    Invariant F-02: amount must be positive if provided.
    Invariant F-11: produces audit history row.
    """
    amount: Decimal | None = Field(default=None, gt=0)
    transaction_type: FinancialTransactionType | None = None
    status: FinancialTransactionStatus | None = None
    category_id: uuid.UUID | None = None
    subcategory_id: uuid.UUID | None = None
    category_source: CategorySource | None = None
    counterparty: str | None = None
    description: str | None = None
    occurred_at: datetime | None = None
    posted_at: datetime | None = None
    tags: list[str] | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: Decimal | None) -> Decimal | None:
        # Invariant F-02: amount always positive
        if v is not None and v <= 0:
            raise ValueError("Invariant F-02: amount must be positive")
        return v


class TransactionResponse(BaseModel):
    """Transaction response with all fields."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    transaction_type: FinancialTransactionType
    status: FinancialTransactionStatus
    amount: Decimal
    signed_amount: Decimal | None
    currency: str
    category_id: uuid.UUID | None
    subcategory_id: uuid.UUID | None
    category_source: CategorySource
    counterparty: str | None
    counterparty_entity_id: uuid.UUID | None
    description: str | None
    occurred_at: datetime
    posted_at: datetime | None
    source: TransactionSource
    external_id: str | None
    transfer_group_id: uuid.UUID | None
    tags: list[str] | None
    is_voided: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int


# =============================================================================
# Transfer Schemas (Session F1-C)
# =============================================================================


class TransferCreate(BaseModel):
    """Create a paired transfer (transfer_out + transfer_in).
    Invariant F-05: exactly 2 records per transfer_group_id.
    """
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal = Field(gt=0, description="Transfer amount (positive, F-02)")
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    description: str | None = None
    occurred_at: datetime | None = None
    status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED
    tags: list[str] | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Invariant F-02: transfer amount must be positive")
        return v

    @model_validator(mode="after")
    def validate_different_accounts(self) -> "TransferCreate":
        if self.from_account_id == self.to_account_id:
            raise ValueError("Transfer source and destination accounts must be different")
        return self


class TransferResponse(BaseModel):
    """Transfer response with both paired transactions."""
    transfer_group_id: uuid.UUID
    transfer_out: TransactionResponse
    transfer_in: TransactionResponse


# =============================================================================
# Balance Computation Schemas (Session F1-C)
# =============================================================================


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


# =============================================================================
# CSV Import Schemas (Session F1-C)
# =============================================================================


class CsvColumnMappingCreate(BaseModel):
    """Save a CSV column mapping for an account."""
    account_id: uuid.UUID
    mapping_name: str = Field(default="default", min_length=1)
    column_mapping: dict[str, str] = Field(
        description="Maps internal field names to CSV column headers. "
        "Keys: date, amount, description, counterparty, category, external_id, balance, transaction_type"
    )


class CsvColumnMappingResponse(BaseModel):
    """Saved CSV column mapping."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    mapping_name: str
    column_mapping: dict[str, str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CsvPreviewRow(BaseModel):
    """A single row in the CSV preview."""
    row_number: int
    data: dict[str, Any]
    transaction: TransactionCreate | None = None
    errors: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_transaction_id: uuid.UUID | None = None


class CsvPreviewResponse(BaseModel):
    """Preview of CSV import results before confirmation."""
    total_rows: int
    valid_rows: int
    error_rows: int
    duplicate_rows: int
    rows: list[CsvPreviewRow]
    detected_columns: list[str]
    has_balance_column: bool


class CsvImportResult(BaseModel):
    """Result of confirmed CSV import."""
    imported_count: int
    skipped_duplicates: int
    error_count: int
    balance_snapshots_created: int
    transaction_ids: list[uuid.UUID]


# =============================================================================
# Smart Defaults Schemas (Session F1-C)
# =============================================================================


class ManualEntryDefaults(BaseModel):
    """Smart defaults for manual transaction entry.
    Section 5.2: most recently used account, date = today, status = posted.
    """
    last_used_account_id: uuid.UUID | None = None
    last_used_account_title: str | None = None
    default_date: date
    default_status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED
