"""CSV import schemas for the finance domain."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from server.app.domains.finance.schemas.transactions import TransactionCreate


class CsvColumnMappingCreate(BaseModel):
    """Save a CSV column mapping for an account."""
    account_id: uuid.UUID
    mapping_name: str = Field(default="default", min_length=1)
    column_mapping: dict[str, str] = Field(
        description="Maps internal field names to CSV column headers. "
        "Keys: date, amount, description, counterparty, category, external_id, balance, transaction_type"
    )


class CsvColumnMappingResponse(BaseModel):
    """Saved CSV column mapping."""
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    mapping_name: str
    column_mapping: dict[str, str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CsvPreviewRow(BaseModel):
    """A single row in the CSV preview."""
    row_number: int
    data: dict[str, Any]
    transaction: TransactionCreate | None = None
    errors: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_transaction_id: uuid.UUID | None = None


class CsvPreviewResponse(BaseModel):
    """Preview of CSV import results before confirmation."""
    total_rows: int
    valid_rows: int
    error_rows: int
    duplicate_rows: int
    rows: list[CsvPreviewRow]
    detected_columns: list[str]
    has_balance_column: bool


class CsvImportResult(BaseModel):
    """Result of confirmed CSV import."""
    imported_count: int
    skipped_duplicates: int
    error_count: int
    balance_snapshots_created: int
    transaction_ids: list[uuid.UUID]
