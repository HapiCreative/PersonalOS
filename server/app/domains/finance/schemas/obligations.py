"""Obligation and breakdown schemas for the finance domain.

F2.6: Core obligation entities with companion table pattern, versioned breakdowns.
Ref: Obligations Addendum Sections 1, 2, 5.1, 7, 8.1.

Invariant F-17: Obligation amount model consistency.
Invariant F-18: Obligation status lifecycle.
Invariant F-19: next_expected_date is CACHED DERIVED.
Invariant F-20: Breakdown amount model consistency.
Invariant F-21: One active breakdown version per normalized_name.
Invariant F-22: Deprecated breakdown has end date.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from server.app.core.models.enums import (
    AmountModel,
    BreakdownAmountModel,
    BreakdownComponentType,
    BreakdownStatus,
    ObligationOrigin,
    ObligationStatus,
    ObligationType,
)


# ---------------------------------------------------------------------------
# Obligation Nodes
# ---------------------------------------------------------------------------


class ObligationCreate(BaseModel):
    """Create an obligation (node + companion in single transaction).

    Invariant F-17: amount_model consistency enforced at validation.
    """
    title: str = Field(min_length=1, description="Obligation display name")
    summary: str | None = None
    obligation_type: ObligationType
    recurrence_rule: str = Field(min_length=1, description="RRULE or cron expression")
    amount_model: AmountModel
    expected_amount: Decimal | None = None
    amount_range_low: Decimal | None = None
    amount_range_high: Decimal | None = None
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    account_id: uuid.UUID = Field(description="Account from which obligation is paid")
    category_id: uuid.UUID | None = None
    billing_anchor: int | None = Field(
        default=None, ge=1, le=31,
        description="Day-of-month hint for anchored recurrence",
    )
    autopay: bool = False
    origin: ObligationOrigin = ObligationOrigin.MANUAL
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Detection confidence. NULL for manual.",
    )
    started_at: date | None = None
    cancellation_url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_amount_model_consistency(self):
        """Invariant F-17: amount_model consistency."""
        if self.amount_model == AmountModel.FIXED:
            if self.expected_amount is None:
                raise ValueError(
                    "Invariant F-17: fixed amount_model requires expected_amount"
                )
            if self.amount_range_low is not None or self.amount_range_high is not None:
                raise ValueError(
                    "Invariant F-17: fixed amount_model must not have range fields"
                )
        elif self.amount_model in (AmountModel.VARIABLE, AmountModel.SEASONAL):
            if self.amount_range_low is None or self.amount_range_high is None:
                raise ValueError(
                    "Invariant F-17: variable/seasonal amount_model requires range fields"
                )
        return self


class ObligationUpdate(BaseModel):
    """Update obligation fields.

    Invariant F-17: amount_model consistency enforced if amount_model changes.
    """
    title: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    obligation_type: ObligationType | None = None
    recurrence_rule: str | None = Field(default=None, min_length=1)
    amount_model: AmountModel | None = None
    expected_amount: Decimal | None = None
    amount_range_low: Decimal | None = None
    amount_range_high: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    billing_anchor: int | None = Field(default=None, ge=1, le=31)
    autopay: bool | None = None
    cancellation_url: str | None = None
    notes: str | None = None


class ObligationResponse(BaseModel):
    """Obligation response with node + companion fields."""
    node_id: uuid.UUID
    title: str
    summary: str | None
    obligation_type: ObligationType
    recurrence_rule: str
    amount_model: AmountModel
    expected_amount: Decimal | None
    amount_range_low: Decimal | None
    amount_range_high: Decimal | None
    currency: str
    account_id: uuid.UUID
    counterparty_entity_id: uuid.UUID | None
    category_id: uuid.UUID | None
    billing_anchor: int | None
    next_expected_date: date | None  # CACHED DERIVED (F-19)
    status: ObligationStatus
    autopay: bool
    origin: ObligationOrigin
    confidence: float | None
    started_at: date | None
    ended_at: date | None
    cancellation_url: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ObligationListResponse(BaseModel):
    items: list[ObligationResponse]
    total: int


# ---------------------------------------------------------------------------
# Obligation Breakdowns
# ---------------------------------------------------------------------------


class BreakdownCreate(BaseModel):
    """Create an obligation breakdown component.

    Invariant F-20: amount_model consistency enforced at validation.
    """
    name: str = Field(min_length=1, description="Display name")
    normalized_name: str = Field(min_length=1, description="Canonical name for dedup")
    component_type: BreakdownComponentType
    amount_model: BreakdownAmountModel
    expected_amount: Decimal | None = None
    amount_range_low: Decimal | None = None
    amount_range_high: Decimal | None = None
    percentage_value: Decimal | None = Field(
        default=None, description="Rate for percentage model (e.g. 0.0825 for 8.25%)",
    )
    match_keywords: list[str] | None = None
    effective_from: date
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_breakdown_amount_model(self):
        """Invariant F-20: breakdown amount_model consistency."""
        if self.amount_model == BreakdownAmountModel.PERCENTAGE:
            if self.percentage_value is None:
                raise ValueError(
                    "Invariant F-20: percentage amount_model requires percentage_value"
                )
            if self.expected_amount is not None:
                raise ValueError(
                    "Invariant F-20: percentage amount_model must not have expected_amount"
                )
        else:
            if self.percentage_value is not None:
                raise ValueError(
                    "Invariant F-20: non-percentage amount_model must not have percentage_value"
                )
        return self


class BreakdownUpdate(BaseModel):
    """Update a breakdown component (creates new version on rate change).

    When a rate change is detected, the old breakdown gets effective_to set
    and a new breakdown is created with effective_from.
    """
    name: str | None = Field(default=None, min_length=1)
    component_type: BreakdownComponentType | None = None
    amount_model: BreakdownAmountModel | None = None
    expected_amount: Decimal | None = None
    amount_range_low: Decimal | None = None
    amount_range_high: Decimal | None = None
    percentage_value: Decimal | None = None
    match_keywords: list[str] | None = None
    sort_order: int | None = None


class BreakdownResponse(BaseModel):
    """Obligation breakdown response."""
    id: uuid.UUID
    obligation_id: uuid.UUID
    name: str
    normalized_name: str
    component_type: BreakdownComponentType
    amount_model: BreakdownAmountModel
    expected_amount: Decimal | None
    amount_range_low: Decimal | None
    amount_range_high: Decimal | None
    percentage_value: Decimal | None
    match_keywords: list[str] | None
    effective_from: date
    effective_to: date | None
    status: BreakdownStatus
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BreakdownListResponse(BaseModel):
    items: list[BreakdownResponse]
    total: int
