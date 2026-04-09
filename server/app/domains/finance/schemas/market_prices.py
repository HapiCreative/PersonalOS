"""Market price cache schemas for the finance domain.

F2.1: Derived cache for market prices. Purgeable at any time.
Manual entry for MVP; API fetch post-MVP.
Ref: Finance Design Rev 3 Section 4.6.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MarketPriceCreate(BaseModel):
    """Create or upsert a market price entry (manual for MVP)."""
    symbol: str = Field(min_length=1, description="Ticker or asset symbol")
    price: Decimal = Field(gt=0, description="Price (4-decimal precision)")
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    price_date: date
    source: str = Field(min_length=1, description="Price data source identifier")


class MarketPriceResponse(BaseModel):
    """Market price response."""
    id: uuid.UUID
    symbol: str
    price: Decimal
    currency: str
    price_date: date
    source: str
    fetched_at: datetime

    model_config = {"from_attributes": True}


class MarketPriceListResponse(BaseModel):
    items: list[MarketPriceResponse]
    total: int
