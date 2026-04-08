"""
Finance Phase F2 — Derived Rollup Tables.

F2.3: Daily, weekly, monthly, and portfolio rollups.
All rollups are Derived — purgeable and recomputable (D-02).
Ref: Finance Design Rev 3 Section 4.8.
"""

import uuid
from datetime import datetime

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from server.app.core.db.database import Base
from server.app.core.models.enums import PortfolioRollupPeriodType


class FinanceDailyRollup(Base):
    """
    Section 4.8: finance_daily_rollups table.
    Refreshed on transaction insert/update (event-driven).
    Derived layer — purgeable and recomputable (D-02).
    """
    __tablename__ = "finance_daily_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    net_worth = mapped_column(Numeric(15, 2), nullable=True)
    liquid_net_worth = mapped_column(Numeric(15, 2), nullable=True)
    total_assets = mapped_column(Numeric(15, 2), nullable=True)
    total_liabilities = mapped_column(Numeric(15, 2), nullable=True)
    daily_income = mapped_column(Numeric(15, 2), nullable=True)
    daily_expenses = mapped_column(Numeric(15, 2), nullable=True)
    daily_net_cashflow = mapped_column(Numeric(15, 2), nullable=True)
    investment_value = mapped_column(Numeric(15, 2), nullable=True)

    __table_args__ = (
        Index("uq_fin_daily_rollup_user_date", "user_id", "date", unique=True),
        Index("idx_fin_daily_rollup_date", "date"),
    )


class FinanceWeeklyRollup(Base):
    """
    Section 4.8: finance_weekly_rollups table.
    Refreshed nightly. Derived layer (D-02).
    """
    __tablename__ = "finance_weekly_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_start_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    total_income = mapped_column(Numeric(15, 2), nullable=True)
    total_expenses = mapped_column(Numeric(15, 2), nullable=True)
    net_cashflow = mapped_column(Numeric(15, 2), nullable=True)
    savings_rate = mapped_column(Numeric(7, 4), nullable=True)
    top_expense_categories: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    category_variance_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    net_worth_start = mapped_column(Numeric(15, 2), nullable=True)
    net_worth_end = mapped_column(Numeric(15, 2), nullable=True)
    net_worth_delta = mapped_column(Numeric(15, 2), nullable=True)

    __table_args__ = (
        Index(
            "uq_fin_weekly_rollup_user_week",
            "user_id", "week_start_date",
            unique=True,
        ),
    )


class FinanceMonthlyRollup(Base):
    """
    Section 4.8: finance_monthly_rollups table.
    Refreshed nightly. Derived layer (D-02).
    """
    __tablename__ = "finance_monthly_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    month: Mapped[datetime] = mapped_column(Date, nullable=False)
    net_worth_start = mapped_column(Numeric(15, 2), nullable=True)
    net_worth_end = mapped_column(Numeric(15, 2), nullable=True)
    net_worth_change = mapped_column(Numeric(15, 2), nullable=True)
    total_income = mapped_column(Numeric(15, 2), nullable=True)
    total_expenses = mapped_column(Numeric(15, 2), nullable=True)
    savings_rate = mapped_column(Numeric(7, 4), nullable=True)
    top_expense_categories: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    investment_return = mapped_column(Numeric(15, 2), nullable=True)
    goal_contributions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_fin_monthly_rollup_user_month",
            "user_id", "month",
            unique=True,
        ),
    )


class PortfolioRollup(Base):
    """
    Section 4.8: portfolio_rollups table.
    Per-account investment performance rollups. Refreshed nightly.
    Derived layer (D-02).
    """
    __tablename__ = "portfolio_rollups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    period_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    period_type: Mapped[PortfolioRollupPeriodType] = mapped_column(nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    total_value = mapped_column(Numeric(15, 2), nullable=True)
    total_cost_basis = mapped_column(Numeric(15, 2), nullable=True)
    unrealized_gain = mapped_column(Numeric(15, 2), nullable=True)
    realized_gain_period = mapped_column(Numeric(15, 2), nullable=True)
    dividend_income_period = mapped_column(Numeric(15, 2), nullable=True)
    deposits_period = mapped_column(Numeric(15, 2), nullable=True)
    withdrawals_period = mapped_column(Numeric(15, 2), nullable=True)
    market_movement = mapped_column(
        Numeric(15, 2), nullable=True,
        comment="total_value change minus deposits plus withdrawals.",
    )
    concentration_top_holding: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index(
            "uq_portfolio_rollup_user_date_type_account",
            "user_id", "period_date", "period_type", "account_id",
            unique=True,
        ),
        Index("idx_portfolio_rollup_account", "account_id"),
        Index("idx_portfolio_rollup_period", "period_date", "period_type"),
    )
