"""Transaction and audit trail schemas for the finance domain."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from server.app.core.models.enums import (
    CategorySource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    TransactionChangeType,
    TransactionSource,
)


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


class ManualEntryDefaults(BaseModel):
    """Smart defaults for manual transaction entry.
    Section 5.2: most recently used account, date = today, status = posted.
    """
    last_used_account_id: uuid.UUID | None = None
    last_used_account_title: str | None = None
    default_date: date
    default_status: FinancialTransactionStatus = FinancialTransactionStatus.POSTED
