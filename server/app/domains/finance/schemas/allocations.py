"""Allocation and goal financial extension schemas for the finance domain."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from server.app.core.models.enums import AllocationType, GoalType


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
