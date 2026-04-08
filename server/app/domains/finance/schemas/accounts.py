"""Account schemas for the finance domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from server.app.core.models.enums import AccountType


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
