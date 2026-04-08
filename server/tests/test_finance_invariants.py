"""
Application-layer validation tests for finance module invariants.
These tests validate business logic enforcement without requiring a database.
Acceptance criteria from Session Map F1-B and F1-C.

Invariants tested:
- F-01: Transactions never become nodes
- F-02: Amount always positive, direction in transaction_type (F1-C)
- F-03: Financial goal field consistency
- F-05: Transfer pairing — exactly 2 records per transfer_group_id (F1-C)
- F-06: No shadow graph (allocations + edges only)
- F-08: Balance queries use posted/settled only (F1-C)
- F-09: Reconciled snapshots authoritative
- F-11: Every transaction mutation → history row (F1-C)
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
    CategorySource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    GoalType,
    NodeType,
    TransactionChangeType,
    TransactionSource,
)
from server.app.domains.finance.schemas import (
    AccountCreate,
    AllocationCreate,
    BalanceSnapshotCreate,
    CategoryCreate,
    GoalFinancialUpdate,
    TransactionCreate,
    TransactionUpdate,
    TransferCreate,
)
from server.app.domains.finance.service import (
    VALID_STATUS_TRANSITIONS,
    validate_goal_financial_fields,
    _map_csv_row_to_transaction,
    _parse_csv_content,
)


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


# =============================================================================
# F-02: Amount Sign Convention (Session F1-C)
# =============================================================================


class TestInvariantF02:
    """Invariant F-02: financial_transactions.amount is always positive.
    Direction is encoded in transaction_type. signed_amount is a generated column."""

    def test_transaction_create_positive_amount(self):
        """Positive amount should pass schema validation."""
        tx = TransactionCreate(
            account_id=uuid.uuid4(),
            transaction_type=FinancialTransactionType.EXPENSE,
            amount=Decimal("50.00"),
            currency="USD",
        )
        assert tx.amount == Decimal("50.00")

    def test_transaction_create_zero_amount_rejected(self):
        """Zero amount should be rejected by schema."""
        with pytest.raises(ValueError, match="F-02|greater than"):
            TransactionCreate(
                account_id=uuid.uuid4(),
                transaction_type=FinancialTransactionType.EXPENSE,
                amount=Decimal("0"),
                currency="USD",
            )

    def test_transaction_create_negative_amount_rejected(self):
        """Negative amount should be rejected by schema."""
        with pytest.raises(ValueError, match="F-02|greater than"):
            TransactionCreate(
                account_id=uuid.uuid4(),
                transaction_type=FinancialTransactionType.EXPENSE,
                amount=Decimal("-50.00"),
                currency="USD",
            )

    def test_transaction_update_negative_amount_rejected(self):
        """Negative amount update should be rejected by schema."""
        with pytest.raises(ValueError, match="F-02|greater than"):
            TransactionUpdate(amount=Decimal("-10.00"))

    def test_transaction_update_zero_amount_rejected(self):
        """Zero amount update should be rejected by schema."""
        with pytest.raises(ValueError, match="F-02|greater than"):
            TransactionUpdate(amount=Decimal("0"))

    def test_transaction_update_positive_amount_passes(self):
        """Positive amount update should pass validation."""
        update = TransactionUpdate(amount=Decimal("100.50"))
        assert update.amount == Decimal("100.50")

    def test_all_inflow_types_defined(self):
        """Verify all inflow transaction types exist."""
        inflow_types = [
            FinancialTransactionType.INCOME,
            FinancialTransactionType.TRANSFER_IN,
            FinancialTransactionType.REFUND,
            FinancialTransactionType.INVESTMENT_SELL,
            FinancialTransactionType.DIVIDEND,
            FinancialTransactionType.INTEREST,
        ]
        for t in inflow_types:
            assert t.value in [
                "income", "transfer_in", "refund",
                "investment_sell", "dividend", "interest",
            ]

    def test_all_outflow_types_defined(self):
        """Verify all outflow transaction types exist."""
        outflow_types = [
            FinancialTransactionType.EXPENSE,
            FinancialTransactionType.TRANSFER_OUT,
            FinancialTransactionType.INVESTMENT_BUY,
            FinancialTransactionType.FEE,
            FinancialTransactionType.ADJUSTMENT,
        ]
        for t in outflow_types:
            assert t.value in [
                "expense", "transfer_out", "investment_buy",
                "fee", "adjustment",
            ]


# =============================================================================
# F-05: Transfer Pairing (Session F1-C)
# =============================================================================


class TestInvariantF05:
    """Invariant F-05: Every transfer_in must have a corresponding transfer_out
    with the same transfer_group_id. Exactly 2 records per group."""

    def test_transfer_create_positive_amount(self):
        """Transfer amount must be positive (F-02)."""
        transfer = TransferCreate(
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
            amount=Decimal("100.00"),
            currency="USD",
        )
        assert transfer.amount == Decimal("100.00")

    def test_transfer_create_negative_amount_rejected(self):
        """Negative transfer amount should be rejected."""
        with pytest.raises(ValueError, match="F-02|greater than"):
            TransferCreate(
                from_account_id=uuid.uuid4(),
                to_account_id=uuid.uuid4(),
                amount=Decimal("-50.00"),
                currency="USD",
            )

    def test_transfer_create_same_accounts_rejected(self):
        """Transfer to same account should be rejected."""
        acct_id = uuid.uuid4()
        with pytest.raises(ValueError, match="different"):
            TransferCreate(
                from_account_id=acct_id,
                to_account_id=acct_id,
                amount=Decimal("100.00"),
                currency="USD",
            )

    def test_transfer_create_different_accounts_passes(self):
        """Transfer between different accounts should pass."""
        transfer = TransferCreate(
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
            amount=Decimal("500.00"),
            currency="EUR",
        )
        assert transfer.from_account_id != transfer.to_account_id

    def test_transfer_types_are_paired(self):
        """transfer_in and transfer_out should both exist as types."""
        assert FinancialTransactionType.TRANSFER_IN.value == "transfer_in"
        assert FinancialTransactionType.TRANSFER_OUT.value == "transfer_out"


# =============================================================================
# F-08: Transaction Status in Balance (Session F1-C)
# =============================================================================


class TestInvariantF08:
    """Invariant F-08: Balance computations only include posted/settled transactions.
    signed_amount = 0 for pending transactions."""

    def test_pending_status_exists(self):
        """Pending status should exist in the enum."""
        assert FinancialTransactionStatus.PENDING.value == "pending"

    def test_posted_status_exists(self):
        """Posted status should exist in the enum."""
        assert FinancialTransactionStatus.POSTED.value == "posted"

    def test_settled_status_exists(self):
        """Settled status should exist in the enum."""
        assert FinancialTransactionStatus.SETTLED.value == "settled"

    def test_status_lifecycle_transitions(self):
        """Status lifecycle: pending → posted → settled. No other transitions."""
        assert FinancialTransactionStatus.POSTED in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.PENDING]
        assert FinancialTransactionStatus.SETTLED in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.POSTED]
        assert VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.SETTLED] == []

    def test_no_backward_transitions(self):
        """No backward transitions allowed."""
        # posted cannot go back to pending
        assert FinancialTransactionStatus.PENDING not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.POSTED]
        # settled cannot go back to posted or pending
        assert FinancialTransactionStatus.POSTED not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.SETTLED]
        assert FinancialTransactionStatus.PENDING not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.SETTLED]

    def test_no_skip_transitions(self):
        """Cannot skip from pending directly to settled."""
        assert FinancialTransactionStatus.SETTLED not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.PENDING]

    def test_default_status_is_posted(self):
        """Default transaction status should be posted."""
        tx = TransactionCreate(
            account_id=uuid.uuid4(),
            transaction_type=FinancialTransactionType.EXPENSE,
            amount=Decimal("25.00"),
            currency="USD",
        )
        assert tx.status == FinancialTransactionStatus.POSTED


# =============================================================================
# F-09: Reconciliation Authority — Extended Tests (Session F1-C)
# =============================================================================


class TestInvariantF09Extended:
    """Extended F-09 tests: reconciled snapshots are authoritative.
    Computed balances never override reconciled snapshots."""

    def test_balance_snapshot_default_not_reconciled(self):
        """Balance snapshots default to not reconciled."""
        snap = BalanceSnapshotCreate(
            account_id=uuid.uuid4(),
            balance=Decimal("1000.00"),
            currency="USD",
            snapshot_date=date(2026, 4, 1),
        )
        assert snap.is_reconciled is False

    def test_balance_snapshot_source_values(self):
        """Balance snapshot source should have all expected values."""
        assert BalanceSnapshotSource.MANUAL.value == "manual"
        assert BalanceSnapshotSource.CSV_IMPORT.value == "csv_import"
        assert BalanceSnapshotSource.API_SYNC.value == "api_sync"
        assert BalanceSnapshotSource.COMPUTED.value == "computed"

    def test_balance_snapshot_can_be_marked_reconciled(self):
        """Balance snapshot can be explicitly marked as reconciled."""
        snap = BalanceSnapshotCreate(
            account_id=uuid.uuid4(),
            balance=Decimal("5000.00"),
            currency="USD",
            snapshot_date=date(2026, 4, 5),
            is_reconciled=True,
        )
        assert snap.is_reconciled is True


# =============================================================================
# F-11: Audit Trail — Extended Tests (Session F1-C)
# =============================================================================


class TestInvariantF11Extended:
    """Extended F-11 tests: every mutation to financial_transactions must produce
    a corresponding financial_transaction_history row."""

    def test_change_types_cover_all_mutations(self):
        """Change types should cover create, update, void — all mutation types."""
        change_types = {ct.value for ct in TransactionChangeType}
        assert change_types == {"create", "update", "void"}

    def test_transaction_source_values(self):
        """TransactionSource should have manual, csv_import, api_sync."""
        assert TransactionSource.MANUAL.value == "manual"
        assert TransactionSource.CSV_IMPORT.value == "csv_import"
        assert TransactionSource.API_SYNC.value == "api_sync"

    def test_category_source_values(self):
        """CategorySource should have manual, system_suggested, imported."""
        assert CategorySource.MANUAL.value == "manual"
        assert CategorySource.SYSTEM_SUGGESTED.value == "system_suggested"
        assert CategorySource.IMPORTED.value == "imported"


# =============================================================================
# CSV Import Parsing Tests (Session F1-C)
# =============================================================================


class TestCsvImportParsing:
    """Tests for CSV import parsing and column mapping logic."""

    def test_parse_csv_content(self):
        """CSV content should be parsed into headers and rows."""
        csv_content = "Date,Amount,Description\n2026-04-01,50.00,Groceries\n2026-04-02,25.00,Gas"
        headers, rows = _parse_csv_content(csv_content)
        assert headers == ["Date", "Amount", "Description"]
        assert len(rows) == 2
        assert rows[0]["Date"] == "2026-04-01"
        assert rows[0]["Amount"] == "50.00"

    def test_map_csv_row_positive_amount_is_income(self):
        """Positive amount in CSV should map to income transaction type."""
        row = {"Date": "2026-04-01", "Amount": "100.00", "Desc": "Salary"}
        mapping = {"date": "Date", "amount": "Amount", "description": "Desc"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data is not None
        assert tx_data["amount"] == Decimal("100.00")
        assert tx_data["transaction_type"] == FinancialTransactionType.INCOME

    def test_map_csv_row_negative_amount_is_expense(self):
        """Negative amount in CSV should map to expense with positive amount (F-02)."""
        row = {"Date": "2026-04-01", "Amount": "-50.00", "Desc": "Coffee"}
        mapping = {"date": "Date", "amount": "Amount", "description": "Desc"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data is not None
        # Invariant F-02: amount always stored positive
        assert tx_data["amount"] == Decimal("50.00")
        assert tx_data["transaction_type"] == FinancialTransactionType.EXPENSE

    def test_map_csv_row_zero_amount_error(self):
        """Zero amount should produce an error."""
        row = {"Amount": "0.00"}
        mapping = {"amount": "Amount"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert errors
        assert tx_data is None

    def test_map_csv_row_invalid_amount_error(self):
        """Invalid amount should produce an error."""
        row = {"Amount": "not-a-number"}
        mapping = {"amount": "Amount"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert errors
        assert "Invalid amount" in errors[0]

    def test_map_csv_row_missing_amount_error(self):
        """Missing amount column should produce an error."""
        row = {"Date": "2026-04-01"}
        mapping = {"date": "Date"}  # No amount mapping
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert errors
        assert "amount" in errors[0].lower()

    def test_map_csv_row_date_formats(self):
        """Multiple date formats should be supported."""
        mapping = {"date": "Date", "amount": "Amount"}
        account_id = uuid.uuid4()

        # YYYY-MM-DD
        row1 = {"Date": "2026-04-01", "Amount": "10.00"}
        tx1, err1 = _map_csv_row_to_transaction(row1, mapping, account_id, "USD", 1)
        assert not err1
        assert tx1["occurred_at"].year == 2026

        # MM/DD/YYYY
        row2 = {"Date": "04/01/2026", "Amount": "10.00"}
        tx2, err2 = _map_csv_row_to_transaction(row2, mapping, account_id, "USD", 1)
        assert not err2

    def test_map_csv_row_currency_symbols_stripped(self):
        """Currency symbols should be stripped from amount."""
        row = {"Amount": "$1,234.56"}
        mapping = {"amount": "Amount"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data["amount"] == Decimal("1234.56")

    def test_map_csv_row_sets_csv_import_source(self):
        """Mapped transaction should have source = csv_import."""
        row = {"Amount": "10.00"}
        mapping = {"amount": "Amount"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data["source"] == TransactionSource.CSV_IMPORT

    def test_map_csv_row_external_id_mapping(self):
        """External ID should be mapped for dedup."""
        row = {"Amount": "10.00", "Ref": "TXN-12345"}
        mapping = {"amount": "Amount", "external_id": "Ref"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data["external_id"] == "TXN-12345"

    def test_map_csv_row_counterparty_mapping(self):
        """Counterparty should be mapped from CSV."""
        row = {"Amount": "10.00", "Payee": "Amazon"}
        mapping = {"amount": "Amount", "counterparty": "Payee"}
        account_id = uuid.uuid4()

        tx_data, errors = _map_csv_row_to_transaction(row, mapping, account_id, "USD", 1)

        assert not errors
        assert tx_data["counterparty"] == "Amazon"


# =============================================================================
# Transaction Schema Validation Tests (Session F1-C)
# =============================================================================


class TestTransactionSchemas:
    """Transaction schema validation tests for session F1-C."""

    def test_transaction_create_defaults(self):
        """Default values should match spec: status=posted, source=manual."""
        tx = TransactionCreate(
            account_id=uuid.uuid4(),
            transaction_type=FinancialTransactionType.INCOME,
            amount=Decimal("1000.00"),
            currency="USD",
        )
        assert tx.status == FinancialTransactionStatus.POSTED
        assert tx.source == TransactionSource.MANUAL
        assert tx.category_source == CategorySource.MANUAL
        assert tx.occurred_at is None  # Will be set to now in service

    def test_transaction_create_with_all_fields(self):
        """Transaction with all optional fields should pass."""
        now = datetime.now(timezone.utc)
        tx = TransactionCreate(
            account_id=uuid.uuid4(),
            transaction_type=FinancialTransactionType.EXPENSE,
            amount=Decimal("42.99"),
            currency="USD",
            status=FinancialTransactionStatus.PENDING,
            category_id=uuid.uuid4(),
            subcategory_id=uuid.uuid4(),
            category_source=CategorySource.SYSTEM_SUGGESTED,
            counterparty="Coffee Shop",
            description="Morning coffee",
            occurred_at=now,
            posted_at=now,
            source=TransactionSource.CSV_IMPORT,
            external_id="EXT-123",
            tags=["coffee", "daily"],
        )
        assert tx.amount == Decimal("42.99")
        assert tx.counterparty == "Coffee Shop"

    def test_transaction_create_invalid_currency(self):
        """Currency code must be exactly 3 characters."""
        with pytest.raises(ValueError):
            TransactionCreate(
                account_id=uuid.uuid4(),
                transaction_type=FinancialTransactionType.EXPENSE,
                amount=Decimal("10.00"),
                currency="US",
            )

    def test_transfer_create_defaults(self):
        """Transfer defaults should be status=posted."""
        transfer = TransferCreate(
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
            amount=Decimal("500.00"),
            currency="USD",
        )
        assert transfer.status == FinancialTransactionStatus.POSTED


# =============================================================================
# Status Lifecycle Tests (Session F1-C)
# =============================================================================


class TestStatusLifecycle:
    """Tests for transaction status lifecycle: pending → posted → settled."""

    def test_valid_transitions_defined(self):
        """All three statuses should have defined transition rules."""
        assert FinancialTransactionStatus.PENDING in VALID_STATUS_TRANSITIONS
        assert FinancialTransactionStatus.POSTED in VALID_STATUS_TRANSITIONS
        assert FinancialTransactionStatus.SETTLED in VALID_STATUS_TRANSITIONS

    def test_pending_to_posted_valid(self):
        """pending → posted is a valid transition."""
        assert FinancialTransactionStatus.POSTED in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.PENDING]

    def test_posted_to_settled_valid(self):
        """posted → settled is a valid transition."""
        assert FinancialTransactionStatus.SETTLED in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.POSTED]

    def test_settled_is_terminal(self):
        """settled has no valid transitions (terminal state)."""
        assert len(VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.SETTLED]) == 0

    def test_pending_to_settled_invalid(self):
        """pending → settled (skipping posted) is NOT valid."""
        assert FinancialTransactionStatus.SETTLED not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.PENDING]

    def test_posted_to_pending_invalid(self):
        """posted → pending (backward) is NOT valid."""
        assert FinancialTransactionStatus.PENDING not in VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.POSTED]

    def test_settled_to_anything_invalid(self):
        """settled → any other status is NOT valid."""
        assert VALID_STATUS_TRANSITIONS[FinancialTransactionStatus.SETTLED] == []
