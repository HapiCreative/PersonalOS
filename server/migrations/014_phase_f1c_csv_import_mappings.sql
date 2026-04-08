-- Migration 014: CSV import column mappings (Session F1-C)
-- Stores saved column mappings per account for CSV import workflows.
-- Part of Behavioral layer: capture workflows (Section 5.2).

CREATE TABLE IF NOT EXISTS csv_import_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id      UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    mapping_name    TEXT NOT NULL DEFAULT 'default',
    column_mapping  JSONB NOT NULL,
    -- column_mapping structure:
    -- {
    --   "date": "Transaction Date",
    --   "amount": "Amount",
    --   "description": "Description",
    --   "counterparty": "Payee",
    --   "category": "Category",
    --   "external_id": "Reference",
    --   "balance": "Balance",
    --   "transaction_type": "Type"
    -- }
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(account_id, mapping_name)
);

CREATE INDEX idx_csv_import_mappings_user ON csv_import_mappings(user_id);
CREATE INDEX idx_csv_import_mappings_account ON csv_import_mappings(account_id);
