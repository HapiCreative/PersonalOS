"""Investment holdings and transaction schemas for the finance domain.

F2.1: Snapshot-based holdings, investment transactions with corporate action support.
Ref: Finance Design Rev 3 Sections 3.3–3.4.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from server.app.core.models.enums import (
    BalanceSnapshotSource,
    InvestmentAssetType,
    InvestmentTransactionType,
    TransactionSource,
    ValuationSource,
)


# ---------------------------------------------------------------------------
# Investment Holdings
# ---------------------------------------------------------------------------


class InvestmentHoldingCreate(BaseModel):
    """Create an investment holding snapshot (per account, per date)."""
    account_id: uuid.UUID
    symbol: str = Field(min_length=1, description="Ticker or asset symbol")
    asset_name: str | None = None
    asset_type: InvestmentAssetType
    quantity: Decimal = Field(description="6-decimal precision for fractional/crypto")
    cost_basis: Decimal | None = None
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    as_of_date: date
    source: BalanceSnapshotSource = BalanceSnapshotSource.MANUAL
    valuation_source: ValuationSource


class InvestmentHoldingUpdate(BaseModel):
    """Update an investment holding snapshot."""
    symbol: str | None = Field(default=None, min_length=1)
    asset_name: str | None = None
    asset_type: InvestmentAssetType | None = None
    quantity: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    as_of_date: date | None = None
    source: BalanceSnapshotSource | None = None
    valuation_source: ValuationSource | None = None


class InvestmentHoldingResponse(BaseModel):
    """Investment holding snapshot response."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    symbol: str
    asset_name: str | None
    asset_type: InvestmentAssetType
    quantity: Decimal
    cost_basis: Decimal | None
    currency: str
    as_of_date: date
    source: BalanceSnapshotSource
    valuation_source: ValuationSource
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentHoldingListResponse(BaseModel):
    items: list[InvestmentHoldingResponse]
    total: int


# ---------------------------------------------------------------------------
# Investment Transactions
# ---------------------------------------------------------------------------


class InvestmentTransactionCreate(BaseModel):
    """Create an investment transaction.

    Supports buy, sell, dividend_reinvest, split, merger, spinoff.
    Split transactions adjust quantity and price_per_unit for cost basis integrity.
    """
    account_id: uuid.UUID
    symbol: str = Field(min_length=1)
    transaction_type: InvestmentTransactionType
    quantity: Decimal = Field(description="6-decimal precision")
    price_per_unit: Decimal = Field(description="6-decimal precision")
    total_amount: Decimal
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    occurred_at: datetime
    lot_id: str | None = Field(default=None, description="Post-MVP: tax lot tracking")
    source: TransactionSource = TransactionSource.MANUAL
    external_id: str | None = None
    notes: str | None = None


class InvestmentTransactionUpdate(BaseModel):
    """Update an investment transaction."""
    symbol: str | None = Field(default=None, min_length=1)
    transaction_type: InvestmentTransactionType | None = None
    quantity: Decimal | None = None
    price_per_unit: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    occurred_at: datetime | None = None
    lot_id: str | None = None
    source: TransactionSource | None = None
    notes: str | None = None


class InvestmentTransactionResponse(BaseModel):
    """Investment transaction response."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    symbol: str
    transaction_type: InvestmentTransactionType
    quantity: Decimal
    price_per_unit: Decimal
    total_amount: Decimal
    currency: str
    occurred_at: datetime
    lot_id: str | None
    source: TransactionSource
    external_id: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentTransactionListResponse(BaseModel):
    items: list[InvestmentTransactionResponse]
    total: int
