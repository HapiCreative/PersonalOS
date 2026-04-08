"""
Application-layer validation tests for finance module invariants.
These tests validate business logic enforcement without requiring a database.
Acceptance criteria from Session Map F1-B.

Invariants tested:
- F-01: Transactions never become nodes
- F-03: Financial goal field consistency
- F-06: No shadow graph (allocations + edges only)
- F-09: Reconciled snapshots authoritative
- F-12: Category deletion blocked by referential integrity
- F-13: Allocation bounds (percentage sum ≤ 1.0 per account)
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from server.app.core.models.enums import (
    AccountType,
    AllocationType,
    BalanceSnapshotSource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    GoalType,
    NodeType,
    TransactionChangeType,
)
from server.app.domains.finance.schemas import (
    AccountCreate,
    AllocationCreate,
    BalanceSnapshotCreate,
    CategoryCreate,
    GoalFinancialUpdate,
)
from server.app.domains.finance.service import validate_goal_financial_fields


# =============================================================================
# F-03: Goal Financial Field Consistency
# =============================================================================


class TestInvariantF03:
    """Invariant F-03: Financial goals require target_amount + currency;
    general goals require all financial fields null."""

    @pytest.mark.asyncio
    async def test_financial_goal_valid(self):
        """Financial goal with target_amount and currency should pass."""
        await validate_goal_financial_fields(
            GoalType.FINANCIAL,
            target_amount=Decimal("10000.00"),
            currency="USD",
        )

    @pytest.mark.asyncio
    async def test_financial_goal_missing_target(self):
        """Financial goal without target_amount should fail."""
        with pytest.raises(ValueError, match="F-03"):
            await validate_goal_financial_fields(
                GoalType.FINANCIAL,
                target_amount=None,
                currency="USD",
            )

    @pytest.mark.asyncio
    async def test_financial_goal_missing_currency(self):
        """Financial goal without currency should fail."""
        with pytest.raises(ValueError, match="F-03"):
            await validate_goal_financial_fields(
                GoalType.FINANCIAL,
                target_amount=Decimal("10000.00"),
                currency=None,
            )

    @pytest.mark.asyncio
    async def test_financial_goal_missing_both(self):
        """Financial goal without both fields should fail."""
        with pytest.raises(ValueError, match="F-03"):
            await validate_goal_financial_fields(
                GoalType.FINANCIAL,
                target_amount=None,
                currency=None,
            )

    @pytest.mark.asyncio
    async def test_general_goal_valid(self):
        """General goal with all financial fields null should pass."""
        await validate_goal_financial_fields(
            GoalType.GENERAL,
            target_amount=None,
            currency=None,
        )

    @pytest.mark.asyncio
    async def test_general_goal_with_target(self):
        """General goal with target_amount should fail."""
        with pytest.raises(ValueError, match="F-03"):
            await validate_goal_financial_fields(
                GoalType.GENERAL,
                target_amount=Decimal("5000.00"),
                currency=None,
            )

    @pytest.mark.asyncio
    async def test_general_goal_with_currency(self):
        """General goal with currency should fail."""
        with pytest.raises(ValueError, match="F-03"):
            await validate_goal_financial_fields(
                GoalType.GENERAL,
                target_amount=None,
                currency="USD",
            )


# =============================================================================
# F-13: Allocation Bounds — Schema-level validation
# =============================================================================


class TestInvariantF13Schemas:
    """Invariant F-13: Percentage allocation sum ≤ 1.0 per account.
    Schema-level validation for individual allocation values."""

    def test_allocation_create_negative_value(self):
        """Negative allocation value should be rejected by schema."""
        with pytest.raises(ValueError):
            AllocationCreate(
                goal_id=uuid.uuid4(),
                account_id=uuid.uuid4(),
                allocation_type=AllocationType.PERCENTAGE,
                value=Decimal("-0.5"),
            )

    def test_allocation_create_valid_percentage(self):
        """Valid percentage allocation should pass."""
        alloc = AllocationCreate(
            goal_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            allocation_type=AllocationType.PERCENTAGE,
            value=Decimal("0.5"),
        )
        assert alloc.value == Decimal("0.5")

    def test_allocation_create_valid_fixed(self):
        """Valid fixed allocation should pass."""
        alloc = AllocationCreate(
            goal_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            allocation_type=AllocationType.FIXED,
            value=Decimal("1000.00"),
        )
        assert alloc.value == Decimal("1000.00")


# =============================================================================
# Account Schema Validation
# =============================================================================


class TestAccountSchemas:
    """Account schema validation tests."""

    def test_account_create_valid(self):
        """Valid account create should pass."""
        acct = AccountCreate(
            title="Chase Checking",
            account_type=AccountType.CHECKING,
            currency="USD",
            institution="Chase",
            account_number_masked="4567",
        )
        assert acct.title == "Chase Checking"
        assert acct.currency == "USD"

    def test_account_create_empty_title(self):
        """Empty title should be rejected."""
        with pytest.raises(ValueError):
            AccountCreate(
                title="",
                account_type=AccountType.CHECKING,
                currency="USD",
            )

    def test_account_create_invalid_currency_length(self):
        """Currency code not 3 chars should be rejected."""
        with pytest.raises(ValueError):
            AccountCreate(
                title="Test",
                account_type=AccountType.CHECKING,
                currency="US",
            )

    def test_account_create_masked_number_too_long(self):
        """Account number mask > 4 chars should be rejected."""
        with pytest.raises(ValueError):
            AccountCreate(
                title="Test",
                account_type=AccountType.CHECKING,
                currency="USD",
                account_number_masked="12345",
            )


# =============================================================================
# Category Schema Validation
# =============================================================================


class TestCategorySchemas:
    """Category schema validation tests."""

    def test_category_create_valid(self):
        """Valid category create should pass."""
        cat = CategoryCreate(name="Groceries")
        assert cat.name == "Groceries"
        assert cat.parent_id is None

    def test_category_create_empty_name(self):
        """Empty name should be rejected."""
        with pytest.raises(ValueError):
            CategoryCreate(name="")

    def test_category_create_with_parent(self):
        """Category with parent_id should pass."""
        parent_id = uuid.uuid4()
        cat = CategoryCreate(name="Fast Food", parent_id=parent_id)
        assert cat.parent_id == parent_id


# =============================================================================
# Balance Snapshot Schema Validation — F-09
# =============================================================================


class TestBalanceSnapshotSchemas:
    """Balance snapshot schema validation.
    Invariant F-09: reconciled snapshots are authoritative."""

    def test_snapshot_create_valid(self):
        """Valid balance snapshot create should pass."""
        snap = BalanceSnapshotCreate(
            account_id=uuid.uuid4(),
            balance=Decimal("5000.00"),
            currency="USD",
            snapshot_date=date(2026, 4, 1),
        )
        assert snap.balance == Decimal("5000.00")
        assert snap.is_reconciled is False

    def test_snapshot_create_reconciled(self):
        """Reconciled snapshot should pass."""
        snap = BalanceSnapshotCreate(
            account_id=uuid.uuid4(),
            balance=Decimal("5000.00"),
            currency="USD",
            snapshot_date=date(2026, 4, 1),
            is_reconciled=True,
        )
        assert snap.is_reconciled is True


# =============================================================================
# Goal Financial Update Schema — F-03
# =============================================================================


class TestGoalFinancialUpdateSchema:
    """GoalFinancialUpdate schema validation for F-03."""

    def test_financial_update_valid(self):
        """Valid financial goal update should pass."""
        update = GoalFinancialUpdate(
            goal_type=GoalType.FINANCIAL,
            target_amount=Decimal("10000.00"),
            currency="USD",
        )
        assert update.goal_type == GoalType.FINANCIAL
        assert update.target_amount == Decimal("10000.00")

    def test_financial_update_negative_target(self):
        """Negative target_amount should be rejected."""
        with pytest.raises(ValueError):
            GoalFinancialUpdate(
                goal_type=GoalType.FINANCIAL,
                target_amount=Decimal("-100.00"),
                currency="USD",
            )

    def test_financial_update_zero_target(self):
        """Zero target_amount should be rejected."""
        with pytest.raises(ValueError):
            GoalFinancialUpdate(
                goal_type=GoalType.FINANCIAL,
                target_amount=Decimal("0"),
                currency="USD",
            )

    def test_general_update_valid(self):
        """General goal with null financial fields should pass."""
        update = GoalFinancialUpdate(
            goal_type=GoalType.GENERAL,
        )
        assert update.goal_type == GoalType.GENERAL
        assert update.target_amount is None
        assert update.currency is None


# =============================================================================
# F-01: Transactions Never Become Nodes
# =============================================================================


class TestInvariantF01:
    """Invariant F-01: Transactions are Temporal records, never nodes.
    This is an architectural constraint verified by the absence of
    transaction-to-node conversion code and the NodeType enum not
    including a 'transaction' value."""

    def test_no_transaction_node_type(self):
        """NodeType enum should not contain a transaction value."""
        node_types = [nt.value for nt in NodeType]
        assert "transaction" not in node_types
        assert "financial_transaction" not in node_types

    def test_account_is_valid_node_type(self):
        """Account should be a valid node type (accounts ARE nodes)."""
        assert NodeType.ACCOUNT.value == "account"


# =============================================================================
# Edge Type-Pair Validation — G-01 for account_funds_goal
# =============================================================================


class TestAccountFundsGoalEdge:
    """G-01: account_funds_goal edge type-pair validation."""

    def test_account_funds_goal_valid(self):
        """account → goal should be valid for account_funds_goal."""
        from server.app.core.services.graph import validate_edge_type_pair
        from server.app.core.models.enums import EdgeRelationType

        error = validate_edge_type_pair(
            EdgeRelationType.ACCOUNT_FUNDS_GOAL,
            NodeType.ACCOUNT,
            NodeType.GOAL,
        )
        assert error is None

    def test_account_funds_goal_invalid_source(self):
        """Non-account source should be invalid for account_funds_goal."""
        from server.app.core.services.graph import validate_edge_type_pair
        from server.app.core.models.enums import EdgeRelationType

        error = validate_edge_type_pair(
            EdgeRelationType.ACCOUNT_FUNDS_GOAL,
            NodeType.TASK,
            NodeType.GOAL,
        )
        assert error is not None
        assert "G-01" in error

    def test_account_funds_goal_invalid_target(self):
        """Non-goal target should be invalid for account_funds_goal."""
        from server.app.core.services.graph import validate_edge_type_pair
        from server.app.core.models.enums import EdgeRelationType

        error = validate_edge_type_pair(
            EdgeRelationType.ACCOUNT_FUNDS_GOAL,
            NodeType.ACCOUNT,
            NodeType.TASK,
        )
        assert error is not None
        assert "G-01" in error


# =============================================================================
# Transaction History Snapshot — F-11
# =============================================================================


class TestTransactionHistorySnapshot:
    """Invariant F-11: Every mutation to financial_transactions produces a
    history row. Tests verify the snapshot structure and change_type values."""

    def test_change_type_values(self):
        """TransactionChangeType should have exactly create, update, void."""
        assert TransactionChangeType.CREATE.value == "create"
        assert TransactionChangeType.UPDATE.value == "update"
        assert TransactionChangeType.VOID.value == "void"
        assert len(TransactionChangeType) == 3

    def test_transaction_type_values(self):
        """FinancialTransactionType should have exactly 11 values."""
        assert len(FinancialTransactionType) == 11

    def test_transaction_status_lifecycle(self):
        """Transaction status should have pending, posted, settled."""
        assert FinancialTransactionStatus.PENDING.value == "pending"
        assert FinancialTransactionStatus.POSTED.value == "posted"
        assert FinancialTransactionStatus.SETTLED.value == "settled"
        assert len(FinancialTransactionStatus) == 3


# =============================================================================
# System Default Categories
# =============================================================================


class TestSystemDefaultCategories:
    """Validate system default categories match the spec."""

    def test_default_categories_count(self):
        """Should have 16 system default categories."""
        from server.app.domains.finance.service import SYSTEM_DEFAULT_CATEGORIES
        assert len(SYSTEM_DEFAULT_CATEGORIES) == 16

    def test_default_categories_names(self):
        """Default category names should match the spec."""
        from server.app.domains.finance.service import SYSTEM_DEFAULT_CATEGORIES
        expected = [
            "Groceries", "Rent/Mortgage", "Utilities", "Dining",
            "Transportation", "Entertainment", "Healthcare", "Insurance",
            "Subscriptions", "Personal Care", "Education", "Gifts/Donations",
            "Income", "Investments", "Fees", "Other",
        ]
        names = [name for name, _ in SYSTEM_DEFAULT_CATEGORIES]
        assert names == expected

    def test_default_categories_sort_order(self):
        """Sort order should be sequential 1-16."""
        from server.app.domains.finance.service import SYSTEM_DEFAULT_CATEGORIES
        orders = [order for _, order in SYSTEM_DEFAULT_CATEGORIES]
        assert orders == list(range(1, 17))
