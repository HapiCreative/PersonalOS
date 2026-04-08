"""Transfer schemas for the finance domain."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from server.app.core.models.enums import FinancialTransactionStatus

from server.app.domains.finance.schemas.transactions import TransactionResponse


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
