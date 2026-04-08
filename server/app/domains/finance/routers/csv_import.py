"""CSV import endpoints for the finance domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from server.app.core.auth.dependencies import get_current_user
from server.app.core.db.database import get_db
from server.app.core.models.user import User
from server.app.domains.finance.schemas.csv_import import (
    CsvColumnMappingCreate,
    CsvColumnMappingResponse,
    CsvImportResult,
    CsvPreviewResponse,
    CsvPreviewRow,
)
from server.app.domains.finance.services.csv_import import (
    execute_csv_import,
    get_csv_mappings,
    preview_csv_import,
    save_csv_mapping,
)

router = APIRouter()


@router.post("/csv-import/preview", response_model=CsvPreviewResponse)
async def preview_csv_import_endpoint(
    account_id: uuid.UUID = Query(description="Target account for import"),
    file: UploadFile = File(description="CSV file to import"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Preview CSV import: parse and validate before committing.
    Section 5.2: Preview before commit with error/duplicate highlighting.
    Requires a saved column mapping or uses the account's default mapping.
    """
    csv_content = (await file.read()).decode("utf-8")

    # Try to find saved mapping for this account
    mappings = await get_csv_mappings(db, user.id, account_id)
    if not mappings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No saved column mapping found for this account. "
            "Save a mapping first via POST /api/finance/csv-import/mappings."
        )

    column_mapping = mappings[0].column_mapping

    try:
        result = await preview_csv_import(db, user.id, account_id, csv_content, column_mapping)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return CsvPreviewResponse(
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        error_rows=result["error_rows"],
        duplicate_rows=result["duplicate_rows"],
        rows=[CsvPreviewRow(**r) for r in result["rows"]],
        detected_columns=result["detected_columns"],
        has_balance_column=result["has_balance_column"],
    )


@router.post("/csv-import/preview-with-mapping", response_model=CsvPreviewResponse)
async def preview_csv_import_with_mapping_endpoint(
    account_id: uuid.UUID = Query(description="Target account for import"),
    file: UploadFile = File(description="CSV file to import"),
    mapping: str = Query(description="JSON-encoded column mapping"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Preview CSV import with an inline column mapping (not saved).
    Useful for first-time import or trying different mappings.
    """
    import json

    csv_content = (await file.read()).decode("utf-8")

    try:
        column_mapping = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON in mapping parameter",
        )

    try:
        result = await preview_csv_import(db, user.id, account_id, csv_content, column_mapping)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return CsvPreviewResponse(
        total_rows=result["total_rows"],
        valid_rows=result["valid_rows"],
        error_rows=result["error_rows"],
        duplicate_rows=result["duplicate_rows"],
        rows=[CsvPreviewRow(**r) for r in result["rows"]],
        detected_columns=result["detected_columns"],
        has_balance_column=result["has_balance_column"],
    )


@router.post("/csv-import/execute", response_model=CsvImportResult)
async def execute_csv_import_endpoint(
    account_id: uuid.UUID = Query(description="Target account for import"),
    file: UploadFile = File(description="CSV file to import"),
    save_mapping: bool = Query(default=True, description="Save column mapping for future use"),
    mapping_name: str = Query(default="default", description="Name for saved mapping"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute CSV import: bulk insert transactions, skip duplicates.
    Section 5.2: Bulk insert on confirm. Auto-generate balance_snapshots if balance column present.
    Invariant F-02: amounts always positive.
    Invariant F-11: audit trail for each imported transaction.
    """
    csv_content = (await file.read()).decode("utf-8")

    # Get saved mapping
    mappings = await get_csv_mappings(db, user.id, account_id)
    if not mappings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No saved column mapping found for this account. "
            "Save a mapping first via POST /api/finance/csv-import/mappings."
        )

    column_mapping = mappings[0].column_mapping

    try:
        result = await execute_csv_import(
            db, user.id, account_id, csv_content, column_mapping,
            save_mapping=save_mapping, mapping_name=mapping_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return CsvImportResult(**result)


@router.post("/csv-import/execute-with-mapping", response_model=CsvImportResult)
async def execute_csv_import_with_mapping_endpoint(
    account_id: uuid.UUID = Query(description="Target account for import"),
    file: UploadFile = File(description="CSV file to import"),
    mapping: str = Query(description="JSON-encoded column mapping"),
    save_mapping: bool = Query(default=True, description="Save column mapping for future use"),
    mapping_name: str = Query(default="default", description="Name for saved mapping"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute CSV import with an inline column mapping.
    Section 5.2: Bulk insert on confirm with inline mapping.
    """
    import json

    csv_content = (await file.read()).decode("utf-8")

    try:
        column_mapping = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON in mapping parameter",
        )

    try:
        result = await execute_csv_import(
            db, user.id, account_id, csv_content, column_mapping,
            save_mapping=save_mapping, mapping_name=mapping_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return CsvImportResult(**result)


@router.post("/csv-import/mappings", response_model=CsvColumnMappingResponse, status_code=status.HTTP_201_CREATED)
async def save_csv_mapping_endpoint(
    body: CsvColumnMappingCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a CSV column mapping for an account (upserts by account + mapping_name)."""
    try:
        mapping = await save_csv_mapping(
            db, user.id, body.account_id, body.column_mapping, body.mapping_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return CsvColumnMappingResponse.model_validate(mapping)


@router.get("/csv-import/mappings/{account_id}", response_model=list[CsvColumnMappingResponse])
async def get_csv_mappings_endpoint(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all saved CSV column mappings for an account."""
    mappings = await get_csv_mappings(db, user.id, account_id)
    return [CsvColumnMappingResponse.model_validate(m) for m in mappings]
