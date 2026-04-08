-- Personal OS Phase F1: Finance Module Foundation Schema
-- Session F1-A: Database Schema
-- Implements: account_nodes, goal_nodes extension, goal_allocations, financial_categories,
--             financial_transactions, balance_snapshots, financial_transaction_history
-- Plan Sections: F1.1, F1.2, F1.3
-- Reference: Finance Module Design Rev 3, Sections 2.1–2.6, 3.1–3.2, 3.6
--
-- Invariants enforced at DB level:
--   F-02: signed_amount generation (amount always positive, direction in transaction_type)
--   F-04: balance snapshot uniqueness (one per account per date)
--   F-08: signed_amount pending behavior (pending → signed_amount = 0)
--   F-12: category FK prevents deletion (RESTRICT on financial_transactions.category_id)
--   S-01: Schema comments tagging CACHED DERIVED and BEHAVIORAL TRACKING fields

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Account types (Section 2.1)
CREATE TYPE account_type AS ENUM (
    'checking', 'savings', 'credit_card', 'brokerage',
    'crypto_wallet', 'cash', 'loan', 'mortgage', 'other'
);

-- Goal type discriminator (Section 2.2)
CREATE TYPE goal_type AS ENUM ('general', 'financial');

-- Goal allocation type (Section 2.6)
CREATE TYPE allocation_type AS ENUM ('percentage', 'fixed');

-- Transaction types — all 11 values (Section 3.1)
CREATE TYPE financial_transaction_type AS ENUM (
    'income', 'expense', 'transfer_in', 'transfer_out',
    'investment_buy', 'investment_sell', 'dividend',
    'interest', 'fee', 'refund', 'adjustment'
);

-- Transaction status lifecycle (Section 3.1)
CREATE TYPE financial_transaction_status AS ENUM ('pending', 'posted', 'settled');

-- Category source — how category was assigned (Section 3.1)
CREATE TYPE category_source AS ENUM ('manual', 'system_suggested', 'imported');

-- Transaction source — data origin (Section 3.1)
CREATE TYPE transaction_source AS ENUM ('manual', 'csv_import', 'api_sync');

-- Balance snapshot source (Section 3.2)
CREATE TYPE balance_snapshot_source AS ENUM ('manual', 'csv_import', 'api_sync', 'computed');

-- Transaction history change type (Section 3.6)
CREATE TYPE transaction_change_type AS ENUM ('create', 'update', 'void');

-- =============================================================================
-- ADD 'account' TO nodes.type ENUM (Section 2.1)
-- =============================================================================

ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'account';

-- =============================================================================
-- ADD 'account_funds_goal' TO edge_relation_type ENUM (Section 2.3)
-- =============================================================================

ALTER TYPE edge_relation_type ADD VALUE IF NOT EXISTS 'account_funds_goal';

-- =============================================================================
-- F1.1.1: ACCOUNT_NODES COMPANION TABLE (Section 2.1)
-- =============================================================================
-- Accounts are durable, user-owned entities representing bank accounts,
-- credit cards, brokerages, wallets, and loans. 1:1 with nodes table.

CREATE TABLE account_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    account_type account_type NOT NULL,
    institution TEXT,
    currency TEXT NOT NULL,                  -- ISO 4217
    account_number_masked TEXT,              -- last 4 digits only
    is_active BOOLEAN NOT NULL DEFAULT true,
    notes TEXT
);

-- Indexes
CREATE INDEX idx_account_nodes_type ON account_nodes(account_type);
CREATE INDEX idx_account_nodes_active ON account_nodes(is_active);

-- =============================================================================
-- F1.1.2: GOAL_NODES EXTENSION — Financial Goal Fields (Section 2.2)
-- =============================================================================
-- Adds goal_type discriminator and three nullable financial fields.
-- Invariant F-03: financial goals require target_amount + currency non-null;
--                 general goals require all three financial fields null.
-- Invariant S-01: current_amount is CACHED DERIVED.

ALTER TABLE goal_nodes ADD COLUMN goal_type goal_type NOT NULL DEFAULT 'general';
ALTER TABLE goal_nodes ADD COLUMN target_amount NUMERIC(15,2);
ALTER TABLE goal_nodes ADD COLUMN current_amount NUMERIC(15,2);
ALTER TABLE goal_nodes ADD COLUMN currency TEXT;

COMMENT ON COLUMN goal_nodes.current_amount IS 'CACHED DERIVED: Computed from account allocations via goal_allocations. Invariant S-01.';

-- Invariant F-03 at DB level: CHECK constraint for field consistency
ALTER TABLE goal_nodes ADD CONSTRAINT goal_financial_field_consistency CHECK (
    (goal_type = 'general' AND target_amount IS NULL AND current_amount IS NULL AND currency IS NULL)
    OR
    (goal_type = 'financial' AND target_amount IS NOT NULL AND currency IS NOT NULL)
);

-- =============================================================================
-- F1.1.3: GOAL_ALLOCATIONS TABLE (Section 2.6)
-- =============================================================================
-- Defines what portion of each account's balance contributes toward a financial goal.
-- Solves the double-counting problem.
-- Invariant F-06: No shadow graph — relationships are edges + allocations only.

CREATE TABLE goal_allocations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    goal_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    allocation_type allocation_type NOT NULL,
    value NUMERIC(15,4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One allocation per goal-account pair
    CONSTRAINT uq_goal_allocations_goal_account UNIQUE (goal_id, account_id),

    -- Percentage must be 0.0–1.0; fixed must be positive
    CONSTRAINT goal_allocations_value_check CHECK (
        (allocation_type = 'percentage' AND value >= 0.0 AND value <= 1.0)
        OR
        (allocation_type = 'fixed' AND value >= 0.0)
    )
);

-- Indexes
CREATE INDEX idx_goal_allocations_goal ON goal_allocations(goal_id);
CREATE INDEX idx_goal_allocations_account ON goal_allocations(account_id);

-- updated_at trigger
CREATE TRIGGER trg_goal_allocations_updated_at
    BEFORE UPDATE ON goal_allocations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- F1.1.5: FINANCIAL_CATEGORIES TABLE (Section 2.5)
-- =============================================================================
-- Structured configuration entities with optional hierarchy.
-- Invariant F-12: Category deletion blocked by referential integrity (RESTRICT).

CREATE TABLE financial_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    parent_id UUID REFERENCES financial_categories(id) ON DELETE SET NULL,
    icon TEXT,
    is_system BOOLEAN NOT NULL DEFAULT false,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- No duplicate category names within the same parent per user
    CONSTRAINT uq_financial_categories_user_name_parent UNIQUE (user_id, name, parent_id)
);

-- Indexes
CREATE INDEX idx_financial_categories_user ON financial_categories(user_id);
CREATE INDEX idx_financial_categories_parent ON financial_categories(parent_id) WHERE parent_id IS NOT NULL;

-- =============================================================================
-- SYSTEM-SEEDED DEFAULT CATEGORIES (Section 2.5)
-- =============================================================================
-- These are inserted as system categories (is_system = true) for user_id = NULL.
-- Actual per-user seeding happens in application code on user creation.
-- This function seeds categories for a given user_id.

CREATE OR REPLACE FUNCTION seed_financial_categories(p_user_id UUID)
RETURNS void AS $$
BEGIN
    INSERT INTO financial_categories (id, user_id, name, is_system, sort_order) VALUES
        (uuid_generate_v4(), p_user_id, 'Groceries',        true, 1),
        (uuid_generate_v4(), p_user_id, 'Rent/Mortgage',    true, 2),
        (uuid_generate_v4(), p_user_id, 'Utilities',        true, 3),
        (uuid_generate_v4(), p_user_id, 'Dining',           true, 4),
        (uuid_generate_v4(), p_user_id, 'Transportation',   true, 5),
        (uuid_generate_v4(), p_user_id, 'Entertainment',    true, 6),
        (uuid_generate_v4(), p_user_id, 'Healthcare',       true, 7),
        (uuid_generate_v4(), p_user_id, 'Insurance',        true, 8),
        (uuid_generate_v4(), p_user_id, 'Subscriptions',    true, 9),
        (uuid_generate_v4(), p_user_id, 'Personal Care',    true, 10),
        (uuid_generate_v4(), p_user_id, 'Education',        true, 11),
        (uuid_generate_v4(), p_user_id, 'Gifts/Donations',  true, 12),
        (uuid_generate_v4(), p_user_id, 'Income',           true, 13),
        (uuid_generate_v4(), p_user_id, 'Investments',      true, 14),
        (uuid_generate_v4(), p_user_id, 'Fees',             true, 15),
        (uuid_generate_v4(), p_user_id, 'Other',            true, 16)
    ON CONFLICT (user_id, name, parent_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- F1.2.1: FINANCIAL_TRANSACTIONS TABLE (Section 3.1)
-- =============================================================================
-- Canonical record of all cash flow events.
-- Invariant F-02: amount always positive, direction encoded in transaction_type.
-- Invariant F-08: signed_amount = 0 for pending transactions.
-- Invariant F-12: category_id REFERENCES financial_categories with RESTRICT.

CREATE TABLE financial_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    transaction_type financial_transaction_type NOT NULL,
    status financial_transaction_status NOT NULL DEFAULT 'posted',

    -- Invariant F-02: amount is always positive
    amount NUMERIC(15,2) NOT NULL,

    -- Invariant F-02 + F-08: signed_amount generated column
    -- Positive for inflows, negative for outflows. Pending → 0.
    -- CACHED DERIVED (S-01): Recomputable from amount + transaction_type + status.
    signed_amount NUMERIC(15,2) GENERATED ALWAYS AS (
        CASE
            WHEN status = 'pending' THEN 0
            WHEN transaction_type IN ('income', 'transfer_in', 'refund', 'investment_sell', 'dividend', 'interest')
            THEN amount
            ELSE -amount
        END
    ) STORED,

    currency TEXT NOT NULL,                                       -- ISO 4217

    -- Invariant F-12: RESTRICT prevents category deletion while transactions reference it
    category_id UUID REFERENCES financial_categories(id) ON DELETE RESTRICT,
    subcategory_id UUID REFERENCES financial_categories(id) ON DELETE SET NULL,
    category_source category_source NOT NULL DEFAULT 'manual',

    counterparty TEXT,                                            -- Raw merchant string
    counterparty_entity_id UUID,                                  -- FK deferred to Phase F3 (counterparty_entities)
    description TEXT,

    occurred_at TIMESTAMPTZ NOT NULL,
    posted_at TIMESTAMPTZ,

    source transaction_source NOT NULL DEFAULT 'manual',
    external_id TEXT,                                             -- Dedup key from CSV or bank sync
    transfer_group_id UUID,                                       -- Links paired transfer_in/transfer_out
    tags TEXT[],
    is_voided BOOLEAN NOT NULL DEFAULT false,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Invariant F-02: amount must be positive
    CONSTRAINT financial_transactions_amount_positive CHECK (amount > 0)
);

COMMENT ON COLUMN financial_transactions.signed_amount IS 'CACHED DERIVED: Computed from amount * direction sign. Pending → 0. Invariants F-02, F-08, S-01.';

-- Indexes (Section 3.1)
CREATE INDEX idx_fin_tx_account_occurred ON financial_transactions(account_id, occurred_at);
CREATE INDEX idx_fin_tx_user_occurred ON financial_transactions(user_id, occurred_at);
CREATE INDEX idx_fin_tx_account_external ON financial_transactions(account_id, external_id) WHERE external_id IS NOT NULL;
CREATE INDEX idx_fin_tx_transfer_group ON financial_transactions(transfer_group_id) WHERE transfer_group_id IS NOT NULL;
CREATE INDEX idx_fin_tx_category ON financial_transactions(category_id);
CREATE INDEX idx_fin_tx_status ON financial_transactions(status);
CREATE INDEX idx_fin_tx_counterparty_entity ON financial_transactions(counterparty_entity_id) WHERE counterparty_entity_id IS NOT NULL;

-- Unique constraint for external_id dedup (idempotent imports)
CREATE UNIQUE INDEX uq_fin_tx_account_external_id ON financial_transactions(account_id, external_id) WHERE external_id IS NOT NULL;

-- updated_at trigger
CREATE TRIGGER trg_financial_transactions_updated_at
    BEFORE UPDATE ON financial_transactions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- F1.2.2: BALANCE_SNAPSHOTS TABLE (Section 3.2)
-- =============================================================================
-- Point-in-time account balance records.
-- Invariant F-04: UNIQUE(account_id, snapshot_date) — one per account per date.
-- Invariant F-09: Reconciled snapshots are authoritative (enforced at app layer).

CREATE TABLE balance_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    balance NUMERIC(15,2) NOT NULL,
    currency TEXT NOT NULL,                                      -- ISO 4217
    snapshot_date DATE NOT NULL,
    source balance_snapshot_source NOT NULL DEFAULT 'manual',
    is_reconciled BOOLEAN NOT NULL DEFAULT false,
    reconciled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Invariant F-04: one snapshot per account per date
    CONSTRAINT uq_balance_snapshots_account_date UNIQUE (account_id, snapshot_date)
);

-- Indexes
CREATE INDEX idx_balance_snapshots_user ON balance_snapshots(user_id);
CREATE INDEX idx_balance_snapshots_account ON balance_snapshots(account_id);
CREATE INDEX idx_balance_snapshots_date ON balance_snapshots(account_id, snapshot_date);

-- =============================================================================
-- F1.3.1: FINANCIAL_TRANSACTION_HISTORY TABLE (Section 3.6)
-- =============================================================================
-- Immutable audit log of all changes to financial_transactions.
-- Invariant F-11: Every mutation produces a history row. Append-only.

CREATE TABLE financial_transaction_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID NOT NULL REFERENCES financial_transactions(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot JSONB NOT NULL,                                      -- Full transaction state
    change_type transaction_change_type NOT NULL,
    changed_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_fin_tx_history_transaction ON financial_transaction_history(transaction_id);
CREATE INDEX idx_fin_tx_history_changed_at ON financial_transaction_history(changed_at);

-- Prevent updates and deletes on history table (append-only invariant F-11)
CREATE OR REPLACE FUNCTION prevent_history_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Invariant F-11: financial_transaction_history is append-only. Updates and deletes are not allowed.';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_history_update
    BEFORE UPDATE ON financial_transaction_history
    FOR EACH ROW
    EXECUTE FUNCTION prevent_history_mutation();

CREATE TRIGGER trg_prevent_history_delete
    BEFORE DELETE ON financial_transaction_history
    FOR EACH ROW
    EXECUTE FUNCTION prevent_history_mutation();

-- =============================================================================
-- UPDATE EDGE TYPE-PAIR CONSTRAINT TRIGGER (Invariant G-01)
-- =============================================================================
-- Add account_funds_goal validation to the existing trigger.

CREATE OR REPLACE FUNCTION validate_edge_type_pair()
RETURNS TRIGGER AS $$
DECLARE
    source_type node_type;
    target_type node_type;
    source_owner UUID;
    target_owner UUID;
    valid BOOLEAN := FALSE;
BEGIN
    -- Fetch source and target node types and owners
    SELECT type, owner_id INTO source_type, source_owner FROM nodes WHERE id = NEW.source_id;
    SELECT type, owner_id INTO target_type, target_owner FROM nodes WHERE id = NEW.target_id;

    IF source_type IS NULL OR target_type IS NULL THEN
        RAISE EXCEPTION 'Source or target node not found';
    END IF;

    -- Invariant G-03: Same-owner edge constraint
    IF source_owner != target_owner THEN
        RAISE EXCEPTION 'Invariant G-03: Edges must connect nodes with the same owner. source_owner=%, target_owner=%', source_owner, target_owner;
    END IF;

    -- Invariant G-01: Edge type-pair constraints
    CASE NEW.relation_type
        WHEN 'parent_child' THEN
            valid := (source_type = 'task' AND target_type = 'task')
                  OR (source_type = 'goal' AND target_type = 'goal');
        WHEN 'belongs_to' THEN
            valid := (source_type = 'goal' AND target_type = 'project')
                  OR (source_type = 'task' AND target_type = 'project');
        WHEN 'goal_tracks_task' THEN
            valid := (source_type = 'goal' AND target_type = 'task');
        WHEN 'goal_tracks_kb' THEN
            valid := (source_type = 'goal' AND target_type = 'kb_entry');
        WHEN 'blocked_by' THEN
            valid := (source_type = 'task' AND target_type = 'task')
                  OR (source_type = 'task' AND target_type = 'goal');
        WHEN 'journal_reflects_on' THEN
            valid := (source_type = 'journal_entry');
        WHEN 'derived_from_source' THEN
            valid := (target_type = 'source_item')
                  AND source_type IN ('kb_entry', 'task', 'memory');
        WHEN 'source_supports_goal' THEN
            valid := (source_type = 'source_item' AND target_type = 'goal');
        WHEN 'source_quoted_in' THEN
            valid := (source_type = 'source_item' AND target_type = 'kb_entry');
        WHEN 'captured_for' THEN
            valid := (source_type = 'source_item');
        -- Finance: account_funds_goal (Section 2.3)
        WHEN 'account_funds_goal' THEN
            valid := (source_type = 'account' AND target_type = 'goal');
        WHEN 'semantic_reference' THEN
            valid := FALSE;

            -- journal_entry -> any
            IF source_type = 'journal_entry' THEN
                valid := TRUE;
            -- kb_entry <-> kb_entry
            ELSIF source_type = 'kb_entry' AND target_type = 'kb_entry' THEN
                valid := TRUE;
            -- kb_entry <-> memory
            ELSIF (source_type = 'kb_entry' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'kb_entry') THEN
                valid := TRUE;
            -- kb_entry <-> source_item
            ELSIF (source_type = 'kb_entry' AND target_type = 'source_item')
               OR (source_type = 'source_item' AND target_type = 'kb_entry') THEN
                valid := TRUE;
            -- memory <-> memory
            ELSIF source_type = 'memory' AND target_type = 'memory' THEN
                valid := TRUE;
            -- goal <-> kb_entry
            ELSIF (source_type = 'goal' AND target_type = 'kb_entry')
               OR (source_type = 'kb_entry' AND target_type = 'goal') THEN
                valid := TRUE;
            -- goal <-> memory
            ELSIF (source_type = 'goal' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'goal') THEN
                valid := TRUE;
            -- task <-> kb_entry
            ELSIF (source_type = 'task' AND target_type = 'kb_entry')
               OR (source_type = 'kb_entry' AND target_type = 'task') THEN
                valid := TRUE;
            -- task <-> memory
            ELSIF (source_type = 'task' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'task') THEN
                valid := TRUE;
            END IF;
        ELSE
            valid := FALSE;
    END CASE;

    IF NOT valid THEN
        RAISE EXCEPTION 'Invariant G-01: Invalid edge type-pair. relation_type=% not allowed for source_type=% -> target_type=%',
            NEW.relation_type, source_type, target_type;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: The trigger trg_validate_edge_type_pair already exists on the edges table
-- from 001_initial_schema.sql. Replacing the function updates the trigger behavior.
