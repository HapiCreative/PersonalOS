"""
Finance Phase F2 — Investment Holdings, Exchange Rates, Market Prices.

F2.1: Core investment tables and rate/price caches.
Ref: Finance Design Rev 3 Sections 3.3–3.5, 4.6.
"""

import uuid
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import (
    BalanceSnapshotSource,
    InvestmentAssetType,
    InvestmentTransactionType,
    TransactionSource,
    ValuationSource,
)


class InvestmentHolding(Base):
    """
    Section 3.3: investment_holdings table.
    Per-account, per-date snapshot of investment positions.
    """
    __tablename__ = "investment_holdings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    asset_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_type: Mapped[InvestmentAssetType] = mapped_column(nullable=False)
    quantity = mapped_column(Numeric(15, 6), nullable=False)  # 6 decimals for fractional/crypto
    cost_basis = mapped_column(Numeric(15, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    as_of_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[BalanceSnapshotSource] = mapped_column(
        nullable=False, default=BalanceSnapshotSource.MANUAL,
    )
    valuation_source: Mapped[ValuationSource] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    __table_args__ = (
        Index("idx_inv_holdings_user", "user_id"),
        Index("idx_inv_holdings_account", "account_id"),
        Index("idx_inv_holdings_symbol", "symbol"),
        Index("idx_inv_holdings_as_of", "account_id", "as_of_date"),
    )


class InvestmentTransaction(Base):
    """
    Section 3.4: investment_transactions table.
    Tracks buy/sell/corporate-action events for investment accounts.
    Partial unique on external_id for idempotent imports.
    """
    __tablename__ = "investment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    transaction_type: Mapped[InvestmentTransactionType] = mapped_column(nullable=False)
    quantity = mapped_column(Numeric(15, 6), nullable=False)
    price_per_unit = mapped_column(Numeric(15, 6), nullable=False)
    total_amount = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)  # ISO 4217
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    lot_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Post-MVP: tax lot tracking.",
    )
    source: Mapped[TransactionSource] = mapped_column(
        nullable=False, default=TransactionSource.MANUAL,
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    __table_args__ = (
        # Partial unique for idempotent imports
        Index(
            "uq_inv_tx_account_external_id",
            "account_id", "external_id",
            unique=True,
            postgresql_where="external_id IS NOT NULL",
        ),
        Index("idx_inv_tx_user", "user_id"),
        Index("idx_inv_tx_account_occurred", "account_id", "occurred_at"),
        Index("idx_inv_tx_symbol", "symbol"),
    )


class ExchangeRate(Base):
    """
    Section 3.5: exchange_rates table.
    Historical currency exchange rates, one per pair per date.
    Invariant F-10: historical net worth always uses rate from snapshot date.
    """
    __tablename__ = "exchange_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    base_currency: Mapped[str] = mapped_column(Text, nullable=False)
    quote_currency: Mapped[str] = mapped_column(Text, nullable=False)
    rate = mapped_column(Numeric(15, 8), nullable=False)
    rate_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    __table_args__ = (
        # Invariant F-10: one rate per currency pair per date
        Index(
            "uq_exchange_rates_pair_date",
            "base_currency", "quote_currency", "rate_date",
            unique=True,
        ),
        Index("idx_exchange_rates_date", "rate_date"),
    )


class MarketPrice(Base):
    """
    Section 4.6: market_prices cache table.
    Derived cache — purgeable at any time.
    Manual entry for MVP; API fetch post-MVP.
    """
    __tablename__ = "market_prices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    price = mapped_column(Numeric(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    price_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )

    __table_args__ = (
        # One price per symbol per date per source
        Index(
            "uq_market_prices_symbol_date_source",
            "symbol", "price_date", "source",
            unique=True,
        ),
        Index("idx_market_prices_symbol", "symbol"),
        Index("idx_market_prices_date", "price_date"),
    )
