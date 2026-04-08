"""CSV import service functions for the finance domain."""

import csv
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.models.enums import (
    BalanceSnapshotSource,
    CategorySource,
    FinancialTransactionStatus,
    FinancialTransactionType,
    NodeType,
    TransactionSource,
)
from server.app.core.models.node import CsvImportMapping, FinancialTransaction, Node
from server.app.domains.finance.services.accounts import get_account
from server.app.domains.finance.services.balance import create_balance_snapshot
from server.app.domains.finance.services.transactions import create_transaction


async def save_csv_mapping(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    column_mapping: dict[str, str],
    mapping_name: str = "default",
) -> CsvImportMapping:
    """
    Save a CSV column mapping for an account.
    Section 5.2: Save mapping per account for future imports.
    """
    # Verify account ownership
    acct_stmt = select(Node).where(
        Node.id == account_id,
        Node.owner_id == user_id,
        Node.type == NodeType.ACCOUNT,
    )
    acct = (await db.execute(acct_stmt)).scalar_one_or_none()
    if acct is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")

    # Check for existing mapping with same name for this account
    existing_stmt = select(CsvImportMapping).where(
        CsvImportMapping.account_id == account_id,
        CsvImportMapping.mapping_name == mapping_name,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is not None:
        existing.column_mapping = column_mapping
        existing.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return existing

    mapping = CsvImportMapping(
        user_id=user_id,
        account_id=account_id,
        mapping_name=mapping_name,
        column_mapping=column_mapping,
    )
    db.add(mapping)
    await db.flush()
    return mapping


async def get_csv_mappings(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
) -> list[CsvImportMapping]:
    """Get all saved CSV column mappings for an account."""
    stmt = (
        select(CsvImportMapping)
        .where(
            CsvImportMapping.user_id == user_id,
            CsvImportMapping.account_id == account_id,
        )
        .order_by(CsvImportMapping.updated_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _parse_csv_content(csv_content: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content string into headers and rows."""
    reader = csv.DictReader(io.StringIO(csv_content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def _map_csv_row_to_transaction(
    row: dict[str, str],
    column_mapping: dict[str, str],
    account_id: uuid.UUID,
    currency: str,
    row_number: int,
) -> tuple[dict | None, list[str]]:
    """
    Map a single CSV row to transaction fields using the column mapping.
    Returns (transaction_dict, errors).
    Invariant F-02: amount is always positive.
    """
    errors: list[str] = []
    tx_data: dict = {}

    # Required: amount
    amount_col = column_mapping.get("amount")
    if not amount_col or amount_col not in row:
        errors.append(f"Row {row_number}: Missing or unmapped 'amount' column")
        return None, errors

    try:
        raw_amount = row[amount_col].strip().replace(",", "").replace("$", "").replace("\u00a3", "").replace("\u20ac", "")
        amount = Decimal(raw_amount)
        # Invariant F-02: amount always positive
        if amount == 0:
            errors.append(f"Row {row_number}: Amount is zero")
            return None, errors
        # If negative, treat as expense; if positive, treat as income
        if amount < 0:
            tx_data["amount"] = abs(amount)
            tx_data["transaction_type"] = FinancialTransactionType.EXPENSE
        else:
            tx_data["amount"] = amount
            tx_data["transaction_type"] = FinancialTransactionType.INCOME
    except (InvalidOperation, ValueError):
        errors.append(f"Row {row_number}: Invalid amount value '{row.get(amount_col, '')}'")
        return None, errors

    # Override transaction_type if mapped
    type_col = column_mapping.get("transaction_type")
    if type_col and type_col in row and row[type_col].strip():
        raw_type = row[type_col].strip().lower()
        try:
            tx_data["transaction_type"] = FinancialTransactionType(raw_type)
        except ValueError:
            # Try common aliases
            type_aliases = {
                "debit": FinancialTransactionType.EXPENSE,
                "credit": FinancialTransactionType.INCOME,
                "withdrawal": FinancialTransactionType.EXPENSE,
                "deposit": FinancialTransactionType.INCOME,
                "payment": FinancialTransactionType.EXPENSE,
            }
            if raw_type in type_aliases:
                tx_data["transaction_type"] = type_aliases[raw_type]

    # Required: date
    date_col = column_mapping.get("date")
    if date_col and date_col in row and row[date_col].strip():
        raw_date = row[date_col].strip()
        parsed_date = None
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
            try:
                parsed_date = datetime.strptime(raw_date, fmt).replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        if parsed_date is None:
            errors.append(f"Row {row_number}: Cannot parse date '{raw_date}'")
            return None, errors
        tx_data["occurred_at"] = parsed_date
    else:
        tx_data["occurred_at"] = datetime.now(timezone.utc)

    # Optional fields
    desc_col = column_mapping.get("description")
    if desc_col and desc_col in row:
        tx_data["description"] = row[desc_col].strip() or None

    counterparty_col = column_mapping.get("counterparty")
    if counterparty_col and counterparty_col in row:
        tx_data["counterparty"] = row[counterparty_col].strip() or None

    ext_id_col = column_mapping.get("external_id")
    if ext_id_col and ext_id_col in row:
        tx_data["external_id"] = row[ext_id_col].strip() or None

    tx_data["account_id"] = account_id
    tx_data["currency"] = currency
    tx_data["source"] = TransactionSource.CSV_IMPORT
    tx_data["category_source"] = CategorySource.IMPORTED
    tx_data["status"] = FinancialTransactionStatus.POSTED

    return tx_data, errors


async def preview_csv_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    csv_content: str,
    column_mapping: dict[str, str],
) -> dict:
    """
    Preview CSV import: parse rows, detect duplicates, highlight errors.
    Section 5.2: Preview before commit with error/duplicate highlighting.
    Dedup via UNIQUE(account_id, external_id).
    """
    # Verify account ownership and get currency
    acct_result = await get_account(db, user_id, account_id)
    if acct_result is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")
    _, account_node = acct_result

    headers, rows = _parse_csv_content(csv_content)

    # Check for balance column
    balance_col = column_mapping.get("balance")
    has_balance_column = balance_col is not None and balance_col in headers

    preview_rows = []
    valid_count = 0
    error_count = 0
    duplicate_count = 0

    for i, row in enumerate(rows, start=1):
        tx_data, errors = _map_csv_row_to_transaction(
            row, column_mapping, account_id, account_node.currency, i
        )

        is_duplicate = False
        duplicate_tx_id = None

        if tx_data and not errors:
            # Check for duplicates via external_id
            ext_id = tx_data.get("external_id")
            if ext_id:
                dup_stmt = select(FinancialTransaction.id).where(
                    FinancialTransaction.account_id == account_id,
                    FinancialTransaction.external_id == ext_id,
                )
                dup_result = (await db.execute(dup_stmt)).scalar_one_or_none()
                if dup_result is not None:
                    is_duplicate = True
                    duplicate_tx_id = dup_result
                    duplicate_count += 1

        if errors:
            error_count += 1
        elif not is_duplicate:
            valid_count += 1

        preview_rows.append({
            "row_number": i,
            "data": dict(row),
            "transaction": tx_data,
            "errors": errors,
            "is_duplicate": is_duplicate,
            "duplicate_transaction_id": duplicate_tx_id,
        })

    return {
        "total_rows": len(rows),
        "valid_rows": valid_count,
        "error_rows": error_count,
        "duplicate_rows": duplicate_count,
        "rows": preview_rows,
        "detected_columns": headers,
        "has_balance_column": has_balance_column,
    }


async def execute_csv_import(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    csv_content: str,
    column_mapping: dict[str, str],
    save_mapping: bool = True,
    mapping_name: str = "default",
) -> dict:
    """
    Execute CSV import: bulk insert transactions, skip duplicates, auto-generate balance snapshots.
    Section 5.2: Bulk insert on confirm, dedup via UNIQUE(account_id, external_id).
    Invariant F-02: amounts always positive.
    Invariant F-11: audit trail for each imported transaction.
    """
    # Verify account ownership and get currency
    acct_result = await get_account(db, user_id, account_id)
    if acct_result is None:
        raise ValueError(f"Account {account_id} not found or not owned by user")
    _, account_node = acct_result

    headers, rows = _parse_csv_content(csv_content)

    balance_col = column_mapping.get("balance")
    has_balance_column = balance_col is not None and balance_col in headers

    imported_ids: list[uuid.UUID] = []
    skipped_duplicates = 0
    error_count = 0
    balance_snapshots_created = 0

    for i, row in enumerate(rows, start=1):
        tx_data, errors = _map_csv_row_to_transaction(
            row, column_mapping, account_id, account_node.currency, i
        )

        if errors or tx_data is None:
            error_count += 1
            continue

        # Check for duplicate via external_id
        ext_id = tx_data.get("external_id")
        if ext_id:
            dup_stmt = select(FinancialTransaction.id).where(
                FinancialTransaction.account_id == account_id,
                FinancialTransaction.external_id == ext_id,
            )
            dup_result = (await db.execute(dup_stmt)).scalar_one_or_none()
            if dup_result is not None:
                skipped_duplicates += 1
                continue

        # Create the transaction
        tx = await create_transaction(
            db, user_id,
            account_id=tx_data["account_id"],
            transaction_type=tx_data["transaction_type"],
            amount=tx_data["amount"],
            currency=tx_data["currency"],
            status=tx_data.get("status", FinancialTransactionStatus.POSTED),
            counterparty=tx_data.get("counterparty"),
            description=tx_data.get("description"),
            occurred_at=tx_data.get("occurred_at"),
            source=TransactionSource.CSV_IMPORT,
            external_id=ext_id,
            category_source=CategorySource.IMPORTED,
        )
        imported_ids.append(tx.id)

        # Auto-generate balance_snapshot if balance column present
        if has_balance_column and balance_col in row and row[balance_col].strip():
            try:
                raw_balance = row[balance_col].strip().replace(",", "").replace("$", "").replace("\u00a3", "").replace("\u20ac", "")
                balance_value = Decimal(raw_balance)
                snapshot_date = tx_data["occurred_at"].date() if isinstance(tx_data["occurred_at"], datetime) else tx_data["occurred_at"]

                await create_balance_snapshot(
                    db, user_id,
                    account_id=account_id,
                    balance=balance_value,
                    currency=account_node.currency,
                    snapshot_date=snapshot_date,
                    source=BalanceSnapshotSource.CSV_IMPORT,
                    is_reconciled=False,
                )
                balance_snapshots_created += 1
            except (InvalidOperation, ValueError):
                pass  # Skip invalid balance values silently

    # Save mapping for future imports if requested
    if save_mapping:
        await save_csv_mapping(db, user_id, account_id, column_mapping, mapping_name)

    return {
        "imported_count": len(imported_ids),
        "skipped_duplicates": skipped_duplicates,
        "error_count": error_count,
        "balance_snapshots_created": balance_snapshots_created,
        "transaction_ids": imported_ids,
    }
