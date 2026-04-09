"""Exchange rate schemas for the finance domain.

F2.1: Historical currency exchange rates per pair per date.
Invariant F-10: historical net worth always uses rate from snapshot date.
Ref: Finance Design Rev 3 Section 3.5.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExchangeRateCreate(BaseModel):
    """Create or upsert an exchange rate.

    Invariant F-10: historical net worth always uses rate from snapshot date.
    """
    base_currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    quote_currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    rate: Decimal = Field(gt=0, description="Exchange rate (8-decimal precision)")
    rate_date: date
    source: str = Field(min_length=1, description="Rate data source identifier")


class ExchangeRateResponse(BaseModel):
    """Exchange rate response."""
    id: uuid.UUID
    base_currency: str
    quote_currency: str
    rate: Decimal
    rate_date: date
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExchangeRateListResponse(BaseModel):
    items: list[ExchangeRateResponse]
    total: int
