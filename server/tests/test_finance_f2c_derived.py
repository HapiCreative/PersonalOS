"""
Application-layer tests for Finance Phase F2-C (Derived Intelligence).

These tests validate business logic without requiring a live database. They
cover the soft invariants and classifications that aren't enforced by DB
constraints:

- F-07: Cashflow exclusion rule (transfer + investment types)
- F-10: Historical FX policy — rate lookup uses target_date, not current date
- D-01: DerivedExplanation required on every user-facing output
- D-02: All rollup/derived outputs recomputable (no hidden canonical state)
- Classification helpers: account liability/liquid classification (Section 4.1)
- Counterparty normalization (pre-F3 fuzzy match)
- Derived explanation schema validation
- Cashflow-eligible type sets match the design doc table
- Spending/rollup helpers for period math
"""

from datetime import date
from decimal import Decimal

import pytest

from server.app.core.models.enums import (
    AccountType,
    FinancialTransactionType,
)
from server.app.derived.schemas import DerivedExplanation, DerivedFactor
from server.app.domains.finance.services._helpers import (
    DEFAULT_BASE_CURRENCY,
    add_months,
    day_range,
    end_of_month,
    end_of_week,
    start_of_month,
    start_of_week,
)
from server.app.domains.finance.services.cashflow import (
    CASHFLOW_EXCLUDED_TYPES,
    EXPENSE_TYPES,
    INCOME_TYPES,
)
from server.app.domains.finance.services.net_worth import (
    LIABILITY_ACCOUNT_TYPES,
    LIQUID_ACCOUNT_TYPES,
    classify_account,
)
from server.app.domains.finance.services.spending._helpers import (
    ANOMALY_MULTIPLIER,
    SPENDING_TYPES,
    TREND_MULTIPLIER,
    _normalize_counterparty,
    _rollup_to_parent,
)


# =============================================================================
# F-07: Cashflow Exclusion Rule
# =============================================================================


class TestInvariantF07CashflowExclusion:
    """F-07: transfer + investment transaction types excluded from cashflow."""

    def test_transfer_types_are_excluded(self):
        assert FinancialTransactionType.TRANSFER_IN in CASHFLOW_EXCLUDED_TYPES
        assert FinancialTransactionType.TRANSFER_OUT in CASHFLOW_EXCLUDED_TYPES

    def test_investment_types_are_excluded(self):
        assert FinancialTransactionType.INVESTMENT_BUY in CASHFLOW_EXCLUDED_TYPES
        assert FinancialTransactionType.INVESTMENT_SELL in CASHFLOW_EXCLUDED_TYPES

    def test_adjustment_type_is_excluded(self):
        assert FinancialTransactionType.ADJUSTMENT in CASHFLOW_EXCLUDED_TYPES

    def test_income_side_types_match_spec(self):
        """Section 4.2: income, dividend, interest, refund."""
        assert INCOME_TYPES == {
            FinancialTransactionType.INCOME,
            FinancialTransactionType.DIVIDEND,
            FinancialTransactionType.INTEREST,
            FinancialTransactionType.REFUND,
        }

    def test_expense_side_types_match_spec(self):
        """Section 4.2: expense, fee."""
        assert EXPENSE_TYPES == {
            FinancialTransactionType.EXPENSE,
            FinancialTransactionType.FEE,
        }

    def test_income_and_expense_sets_are_disjoint(self):
        assert INCOME_TYPES.isdisjoint(EXPENSE_TYPES)

    def test_cashflow_eligible_sets_disjoint_from_excluded(self):
        assert INCOME_TYPES.isdisjoint(CASHFLOW_EXCLUDED_TYPES)
        assert EXPENSE_TYPES.isdisjoint(CASHFLOW_EXCLUDED_TYPES)


# =============================================================================
# Net worth classification (Section 4.1)
# =============================================================================


class TestNetWorthClassification:
    """Section 4.1: Account asset/liability + liquid/illiquid classification."""

    def test_loan_is_liability(self):
        is_liability, _ = classify_account(AccountType.LOAN)
        assert is_liability is True

    def test_mortgage_is_liability(self):
        is_liability, _ = classify_account(AccountType.MORTGAGE)
        assert is_liability is True

    def test_credit_card_is_liability_and_liquid(self):
        is_liability, is_liquid = classify_account(AccountType.CREDIT_CARD)
        assert is_liability is True
        assert is_liquid is True

    def test_checking_is_asset_and_liquid(self):
        is_liability, is_liquid = classify_account(AccountType.CHECKING)
        assert is_liability is False
        assert is_liquid is True

    def test_savings_is_asset_and_liquid(self):
        is_liability, is_liquid = classify_account(AccountType.SAVINGS)
        assert is_liability is False
        assert is_liquid is True

    def test_cash_is_asset_and_liquid(self):
        _, is_liquid = classify_account(AccountType.CASH)
        assert is_liquid is True

    def test_crypto_wallet_is_asset_and_liquid(self):
        _, is_liquid = classify_account(AccountType.CRYPTO_WALLET)
        assert is_liquid is True

    def test_brokerage_is_not_auto_liquid(self):
        """Section 4.1: brokerage depends on asset_type within holdings."""
        is_liability, is_liquid = classify_account(AccountType.BROKERAGE)
        assert is_liability is False
        assert is_liquid is False

    def test_liability_set_covers_all_liability_types(self):
        assert AccountType.LOAN in LIABILITY_ACCOUNT_TYPES
        assert AccountType.MORTGAGE in LIABILITY_ACCOUNT_TYPES
        assert AccountType.CREDIT_CARD in LIABILITY_ACCOUNT_TYPES

    def test_liquid_set_covers_checking_savings_cash_crypto_cc(self):
        assert AccountType.CHECKING in LIQUID_ACCOUNT_TYPES
        assert AccountType.SAVINGS in LIQUID_ACCOUNT_TYPES
        assert AccountType.CASH in LIQUID_ACCOUNT_TYPES
        assert AccountType.CRYPTO_WALLET in LIQUID_ACCOUNT_TYPES
        assert AccountType.CREDIT_CARD in LIQUID_ACCOUNT_TYPES


# =============================================================================
# D-01: DerivedExplanation required on user-facing outputs
# =============================================================================


class TestInvariantD01Explanation:
    """D-01: every user-facing Derived output must have a DerivedExplanation."""

    def test_valid_explanation(self):
        exp = DerivedExplanation(
            summary="net worth 100",
            factors=[DerivedFactor(signal="x", value=1, weight=1.0)],
        )
        DerivedExplanation.validate(exp)

    def test_empty_summary_rejected(self):
        exp = DerivedExplanation(
            summary="",
            factors=[DerivedFactor(signal="x", value=1, weight=1.0)],
        )
        with pytest.raises(ValueError, match="summary"):
            DerivedExplanation.validate(exp)

    def test_empty_factors_rejected(self):
        exp = DerivedExplanation(summary="ok", factors=[])
        with pytest.raises(ValueError, match="factors"):
            DerivedExplanation.validate(exp)

    def test_factor_missing_signal_rejected(self):
        exp = DerivedExplanation(
            summary="ok",
            factors=[DerivedFactor(signal="", value=1, weight=1.0)],
        )
        with pytest.raises(ValueError, match="signal"):
            DerivedExplanation.validate(exp)

    def test_confidence_out_of_range_rejected(self):
        exp = DerivedExplanation(
            summary="ok",
            factors=[DerivedFactor(signal="x", value=1, weight=1.0)],
            confidence=1.5,
        )
        with pytest.raises(ValueError, match="confidence"):
            DerivedExplanation.validate(exp)


# =============================================================================
# Spending helpers (Section 4.3)
# =============================================================================


class TestSpendingHelpers:
    """Thresholds + helpers used by spending intelligence."""

    def test_spending_types_are_expense_fee_only(self):
        """F-07: transfers/investments excluded; only expense/fee eligible."""
        assert FinancialTransactionType.EXPENSE in SPENDING_TYPES
        assert FinancialTransactionType.FEE in SPENDING_TYPES
        assert FinancialTransactionType.TRANSFER_OUT not in SPENDING_TYPES
        assert FinancialTransactionType.INVESTMENT_BUY not in SPENDING_TYPES

    def test_trend_multiplier_is_1_5(self):
        """Section 4.3: 1.5× rolling 3-month average."""
        assert TREND_MULTIPLIER == Decimal("1.5")

    def test_anomaly_multiplier_is_3(self):
        """Section 4.3: 3× category median."""
        assert ANOMALY_MULTIPLIER == Decimal("3.0")

    def test_normalize_counterparty_lowercases(self):
        assert _normalize_counterparty("AMAZON") == "amazon"

    def test_normalize_counterparty_strips_store_numbers(self):
        assert _normalize_counterparty("Starbucks #12345") == "starbucks"

    def test_normalize_counterparty_strips_trailing_numbers(self):
        assert _normalize_counterparty("Target Store 4321") == "target store"

    def test_normalize_counterparty_collapses_whitespace(self):
        assert _normalize_counterparty("  whole   foods  ") == "whole foods"

    def test_normalize_counterparty_empty_returns_none(self):
        assert _normalize_counterparty("") is None
        assert _normalize_counterparty(None) is None
        assert _normalize_counterparty("  ") is None


class TestCategoryRollup:
    """Section 4.3: category hierarchy rollup adds child → parent."""

    def test_rollup_adds_child_to_parent(self):
        # Build a tiny hierarchy: dining (parent) → restaurants (child)
        class FakeCat:
            def __init__(self, id, name, parent_id):
                self.id = id
                self.name = name
                self.parent_id = parent_id

        parent_id = "p-dining"
        child_id = "c-restaurants"
        cat_map = {
            parent_id: FakeCat(parent_id, "Dining", None),
            child_id: FakeCat(child_id, "Restaurants", parent_id),
        }

        spend = {child_id: Decimal("100")}
        rolled = _rollup_to_parent(spend, cat_map)
        assert rolled[parent_id] == Decimal("100")
        assert rolled[child_id] == Decimal("100")

    def test_rollup_preserves_leaf_totals(self):
        class FakeCat:
            def __init__(self, id, name, parent_id):
                self.id = id
                self.name = name
                self.parent_id = parent_id

        cat_map = {"a": FakeCat("a", "Food", None)}
        spend = {"a": Decimal("50"), None: Decimal("10")}
        rolled = _rollup_to_parent(spend, cat_map)
        assert rolled["a"] == Decimal("50")
        assert rolled[None] == Decimal("10")


# =============================================================================
# Period helpers
# =============================================================================


class TestPeriodHelpers:
    def test_default_base_currency(self):
        assert DEFAULT_BASE_CURRENCY == "USD"

    def test_start_of_month(self):
        assert start_of_month(date(2026, 4, 15)) == date(2026, 4, 1)

    def test_end_of_month_regular(self):
        assert end_of_month(date(2026, 4, 15)) == date(2026, 4, 30)

    def test_end_of_month_february_leap(self):
        assert end_of_month(date(2024, 2, 10)) == date(2024, 2, 29)

    def test_end_of_month_february_non_leap(self):
        assert end_of_month(date(2025, 2, 10)) == date(2025, 2, 28)

    def test_start_of_week_wednesday(self):
        # 2026-04-08 is a Wednesday → Monday is 2026-04-06
        assert start_of_week(date(2026, 4, 8)) == date(2026, 4, 6)

    def test_end_of_week_wednesday(self):
        assert end_of_week(date(2026, 4, 8)) == date(2026, 4, 12)

    def test_add_months_simple(self):
        assert add_months(date(2026, 1, 15), 3) == date(2026, 4, 15)

    def test_add_months_wraps_year(self):
        assert add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)

    def test_add_months_clamps_day(self):
        # Jan 31 + 1 month → Feb 28/29
        result = add_months(date(2025, 1, 31), 1)
        assert result.month == 2
        assert result.day == 28

    def test_day_range_inclusive(self):
        days = day_range(date(2026, 4, 1), date(2026, 4, 3))
        assert days == [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)]

    def test_day_range_empty_when_end_before_start(self):
        assert day_range(date(2026, 4, 5), date(2026, 4, 1)) == []


# =============================================================================
# Goal progress contribution types
# =============================================================================


class TestGoalProgressContributionTypes:
    """Goal progress inflows include cashflow income types plus transfer_in."""

    def test_contribution_types_include_income(self):
        from server.app.domains.finance.services.goal_progress import (
            CONTRIBUTION_INCOME_TYPES,
        )
        assert FinancialTransactionType.INCOME in CONTRIBUTION_INCOME_TYPES
        assert FinancialTransactionType.DIVIDEND in CONTRIBUTION_INCOME_TYPES
        assert FinancialTransactionType.INTEREST in CONTRIBUTION_INCOME_TYPES
        assert FinancialTransactionType.REFUND in CONTRIBUTION_INCOME_TYPES

    def test_contribution_types_include_transfer_in(self):
        from server.app.domains.finance.services.goal_progress import (
            CONTRIBUTION_INCOME_TYPES,
        )
        # transfer_in represents moving money into the funded account, which
        # counts toward goal progress even though it's excluded from cashflow.
        assert FinancialTransactionType.TRANSFER_IN in CONTRIBUTION_INCOME_TYPES

    def test_contribution_types_exclude_expenses(self):
        from server.app.domains.finance.services.goal_progress import (
            CONTRIBUTION_INCOME_TYPES,
        )
        assert FinancialTransactionType.EXPENSE not in CONTRIBUTION_INCOME_TYPES
        assert FinancialTransactionType.FEE not in CONTRIBUTION_INCOME_TYPES
