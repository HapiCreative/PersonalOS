"""
Finance Phase F2-C — Derived Intelligence response schemas.

Response shapes for net worth, cashflow, spending, goal progress,
investment performance, and rollup endpoints.

Every user-facing output includes a DerivedExplanation (Invariant D-01).
Every output is recomputable (Invariant D-02) — nothing stored here is
canonical; tables are stateful projections only.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# DerivedExplanation response (Invariant D-01)
# =============================================================================


class DerivedFactorResponse(BaseModel):
    """Section 4.11: single contributing factor in a DerivedExplanation."""
    signal: str
    value: Any
    weight: float


class DerivedExplanationResponse(BaseModel):
    """
    Section 4.11: DerivedExplanation schema type.
    Invariant D-01: required on all user-facing Derived outputs.
    """
    summary: str
    factors: list[DerivedFactorResponse]
    confidence: float | None = None
    generated_at: str | None = None
    version: str | None = None


# =============================================================================
# Net Worth (Section 4.1)
# =============================================================================


class AccountBalanceBreakdown(BaseModel):
    """Per-account contribution to net worth. Currency-converted to base."""
    account_id: UUID
    account_name: str
    account_type: str
    native_balance: Decimal
    native_currency: str
    base_balance: Decimal
    base_currency: str
    exchange_rate: Decimal
    is_liability: bool
    is_liquid: bool
    snapshot_date: date | None


class NetWorthResponse(BaseModel):
    """
    Section 4.1: Net worth engine output.
    Invariant F-10: historical FX uses snapshot-date rates.
    Invariant D-01: DerivedExplanation required.
    """
    as_of_date: date
    base_currency: str
    net_worth: Decimal
    liquid_net_worth: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    liquid_assets: Decimal
    illiquid_assets: Decimal
    account_count: int
    breakdown: list[AccountBalanceBreakdown]
    explanation: DerivedExplanationResponse


# =============================================================================
# Cashflow Analytics (Section 4.2)
# =============================================================================


class CashflowResponse(BaseModel):
    """
    Section 4.2: Cashflow analytics output.
    Invariant F-07: transfer + investment types excluded.
    Invariant D-01: DerivedExplanation required.
    """
    period_start: date
    period_end: date
    days_in_period: int
    monthly_income: Decimal = Field(description="SUM(signed_amount) for income-side types")
    monthly_expenses: Decimal = Field(description="SUM(ABS(signed_amount)) for expense-side types")
    net_cashflow: Decimal
    savings_rate: float | None = Field(description="net_cashflow / monthly_income, or null if no income")
    burn_rate: Decimal = Field(description="monthly_expenses / 30 (daily average)")
    pending_income: Decimal = Field(default=Decimal("0"))
    pending_expenses: Decimal = Field(default=Decimal("0"))
    transaction_count: int
    explanation: DerivedExplanationResponse


# =============================================================================
# Spending Intelligence (Section 4.3)
# =============================================================================


class CategoryBreakdownEntry(BaseModel):
    category_id: UUID | None
    category_name: str
    parent_category_id: UUID | None
    total_spend: Decimal
    transaction_count: int
    pct_of_total: float
    is_rollup: bool = False


class CategoryBreakdownResponse(BaseModel):
    """Section 4.3: Category breakdown per period with hierarchy rollup."""
    period_start: date
    period_end: date
    total_spend: Decimal
    categories: list[CategoryBreakdownEntry]
    explanation: DerivedExplanationResponse


class CategoryTrendEntry(BaseModel):
    category_id: UUID | None
    category_name: str
    current_month_spend: Decimal
    rolling_3month_avg: Decimal
    ratio: float
    is_trending_up: bool


class SpendingTrendResponse(BaseModel):
    """Section 4.3: Trend detection — 1.5x rolling 3-month average."""
    as_of_date: date
    trending_categories: list[CategoryTrendEntry]
    explanation: DerivedExplanationResponse


class SpendingAnomaly(BaseModel):
    transaction_id: UUID
    account_id: UUID
    category_id: UUID | None
    category_name: str
    amount: Decimal
    currency: str
    occurred_at: str
    category_median: Decimal
    ratio: float
    counterparty: str | None
    explanation: DerivedExplanationResponse


class SpendingAnomalyResponse(BaseModel):
    """Section 4.3: Anomaly detection — 3x category median."""
    period_start: date
    period_end: date
    anomalies: list[SpendingAnomaly]


class MerchantConcentrationEntry(BaseModel):
    counterparty: str
    category_id: UUID | None
    category_name: str
    merchant_spend: Decimal
    category_total: Decimal
    share: float


class MerchantConcentrationResponse(BaseModel):
    """Section 4.3: Merchant concentration — fuzzy match on raw counterparty pre-F3."""
    period_start: date
    period_end: date
    threshold: float
    concentrated_merchants: list[MerchantConcentrationEntry]
    explanation: DerivedExplanationResponse


class SpendCreepEntry(BaseModel):
    category_id: UUID | None
    category_name: str
    earlier_window_avg: Decimal
    later_window_avg: Decimal
    delta_pct: float
    window_months: int


class SpendCreepResponse(BaseModel):
    """Section 4.3: Spend creep — rolling 3-month avg across consecutive windows."""
    as_of_date: date
    creeping_categories: list[SpendCreepEntry]
    explanation: DerivedExplanationResponse


class LeakageCandidateEntry(BaseModel):
    counterparty: str
    category_id: UUID | None
    category_name: str
    total_spend: Decimal
    occurrence_count: int
    avg_amount: Decimal
    first_seen: str
    last_seen: str


class LeakageCandidatesResponse(BaseModel):
    """Section 4.3: Leakage candidates — frequency heuristics pre-F3."""
    period_start: date
    period_end: date
    candidates: list[LeakageCandidateEntry]
    explanation: DerivedExplanationResponse


# =============================================================================
# Financial Goal Progress (Section 4.4)
# =============================================================================


class GoalProgressResponse(BaseModel):
    """Section 4.4: Financial goal progress output."""
    goal_id: UUID
    goal_name: str
    target_amount: Decimal
    current_amount: Decimal
    currency: str
    progress_pct: float
    end_date: date | None
    days_remaining: int | None
    monthly_contribution_rate: Decimal | None = Field(
        description="Linear projection from last 90 days of contributions"
    )
    projected_completion_date: date | None
    monthly_contribution_needed: Decimal | None
    is_on_track: bool | None
    allocation_count: int
    explanation: DerivedExplanationResponse


class GoalProgressListResponse(BaseModel):
    goals: list[GoalProgressResponse]


# =============================================================================
# Investment Performance (Section 4.5)
# =============================================================================


class HoldingPerformance(BaseModel):
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    current_price: Decimal | None
    total_value: Decimal | None
    unrealized_gain: Decimal | None
    asset_type: str
    currency: str


class InvestmentPerformanceResponse(BaseModel):
    """
    Section 4.5: Investment performance metrics.
    Realized gain uses average cost basis pre-F4 (lot tracking deferred).
    """
    account_id: UUID | None = Field(description="Null = aggregate across all investment accounts")
    account_name: str | None
    as_of_date: date
    base_currency: str
    total_value: Decimal
    total_cost_basis: Decimal
    total_invested: Decimal
    unrealized_gain: Decimal
    realized_gain: Decimal
    simple_return: float | None
    dividend_income: Decimal
    holdings: list[HoldingPerformance]
    explanation: DerivedExplanationResponse


# =============================================================================
# Rollup Tables (Section 4.8)
# =============================================================================


class FinanceDailyRollupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    date: date
    net_worth: Decimal | None
    liquid_net_worth: Decimal | None
    total_assets: Decimal | None
    total_liabilities: Decimal | None
    daily_income: Decimal | None
    daily_expenses: Decimal | None
    daily_net_cashflow: Decimal | None
    investment_value: Decimal | None


class FinanceWeeklyRollupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    week_start_date: date
    week_end_date: date
    total_income: Decimal | None
    total_expenses: Decimal | None
    net_cashflow: Decimal | None
    savings_rate: Decimal | None
    top_expense_categories: list[dict] | None
    category_variance_flags: list[dict] | None
    net_worth_start: Decimal | None
    net_worth_end: Decimal | None
    net_worth_delta: Decimal | None


class FinanceMonthlyRollupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    month: date
    net_worth_start: Decimal | None
    net_worth_end: Decimal | None
    net_worth_change: Decimal | None
    total_income: Decimal | None
    total_expenses: Decimal | None
    savings_rate: Decimal | None
    top_expense_categories: list[dict] | None
    investment_return: Decimal | None
    goal_contributions: list[dict] | None


class PortfolioRollupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    period_date: date
    period_type: Literal["daily", "monthly"]
    account_id: UUID
    total_value: Decimal | None
    total_cost_basis: Decimal | None
    unrealized_gain: Decimal | None
    realized_gain_period: Decimal | None
    dividend_income_period: Decimal | None
    deposits_period: Decimal | None
    withdrawals_period: Decimal | None
    market_movement: Decimal | None
    concentration_top_holding: dict | None


class RollupRefreshResponse(BaseModel):
    """Response shape for manual rollup refresh requests."""
    daily_count: int = 0
    weekly_count: int = 0
    monthly_count: int = 0
    portfolio_count: int = 0
    goal_progress_updated: int = 0
    start_date: date
    end_date: date
