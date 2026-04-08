-- Personal OS Phase F2-A: Finance Module — All Phase F2 Database Schema
-- Session F2-A: Database Schema Only
-- Implements:
--   F2.1: investment_holdings, investment_transactions, exchange_rates, market_prices
--   F2.3: finance_daily_rollups, finance_weekly_rollups, finance_monthly_rollups, portfolio_rollups
--   F2.4: finance_alerts
--   F2.6: obligation_nodes, obligation_breakdowns, edge type-pair updates, semantic_reference updates
-- Reference: Finance Design Rev 3, Obligations Addendum
--
-- Invariants enforced at DB level:
--   F-10: exchange_rates UNIQUE(base_currency, quote_currency, rate_date)
--   F-14: finance_alerts dedup via UNIQUE(user_id, dedup_key)
--   F-17: obligation amount_model consistency (CHECK)
--   F-18: obligation status lifecycle (CHECK)
--   F-20: breakdown amount_model consistency (CHECK)
--   F-21: partial unique on (obligation_id, normalized_name) WHERE effective_to IS NULL
--   F-22: deprecated breakdown requires effective_to (CHECK)
--   S-01: Schema comments tagging CACHED DERIVED fields

-- =============================================================================
-- NEW ENUMS
-- =============================================================================

-- Investment asset types (Section 3.3)
CREATE TYPE investment_asset_type AS ENUM (
    'stock', 'etf', 'mutual_fund', 'bond', 'crypto', 'option', 'other'
);

-- Investment transaction types (Section 3.4)
CREATE TYPE investment_transaction_type AS ENUM (
    'buy', 'sell', 'dividend_reinvest', 'split', 'merger', 'spinoff'
);

-- Valuation source (Section 3.3)
CREATE TYPE valuation_source AS ENUM ('market_api', 'manual', 'computed');

-- Obligation types (Obligations Addendum Section 2)
CREATE TYPE obligation_type AS ENUM (
    'subscription', 'utility', 'rent', 'loan', 'insurance', 'tax', 'membership', 'other'
);

-- Amount model (Obligations Addendum Section 2)
CREATE TYPE amount_model AS ENUM ('fixed', 'variable', 'seasonal');

-- Obligation status (Obligations Addendum Section 2)
CREATE TYPE obligation_status AS ENUM ('active', 'paused', 'cancelled');

-- Obligation origin (Obligations Addendum Section 2)
CREATE TYPE obligation_origin AS ENUM ('manual', 'detected');

-- Breakdown component types (Obligations Addendum Section 2)
CREATE TYPE breakdown_component_type AS ENUM (
    'base', 'usage', 'tax', 'fee', 'discount', 'adjustment', 'other'
);

-- Breakdown amount model — extends amount_model with percentage (Obligations Addendum Section 2)
CREATE TYPE breakdown_amount_model AS ENUM ('fixed', 'variable', 'seasonal', 'percentage');

-- Breakdown status (Obligations Addendum Section 2)
CREATE TYPE breakdown_status AS ENUM ('active', 'deprecated');

-- Finance alert types (Section 5.1 + Obligations Addendum Section 5)
CREATE TYPE alert_type AS ENUM (
    -- Rule-based (F2.4)
    'low_cash_runway', 'large_transaction', 'uncategorized_aging',
    'duplicate_import', 'stale_pending', 'goal_off_track',
    'unreconciled_divergence', 'broken_transfer',
    -- Rule-based obligation alerts (F2.6)
    'upcoming_obligation', 'missed_obligation', 'obligation_amount_spike',
    'obligation_rate_change', 'obligation_expiring'
);

-- Finance alert severity (Section 5.1)
CREATE TYPE alert_severity AS ENUM ('high', 'medium', 'low');

-- Finance alert status lifecycle (Section 5.1)
CREATE TYPE alert_status AS ENUM ('active', 'dismissed', 'snoozed', 'resolved');

-- Portfolio rollup period type (Section 4.8)
CREATE TYPE portfolio_rollup_period_type AS ENUM ('daily', 'monthly');

-- =============================================================================
-- ADD 'obligation' TO nodes.type ENUM (Obligations Addendum Section 2)
-- =============================================================================

ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'obligation';

-- =============================================================================
-- ADD OBLIGATION EDGE RELATIONS (Obligations Addendum Section 2)
-- =============================================================================

ALTER TYPE edge_relation_type ADD VALUE IF NOT EXISTS 'obligation_charges_account';
ALTER TYPE edge_relation_type ADD VALUE IF NOT EXISTS 'obligation_impacts_goal';

-- =============================================================================
-- F2.1.1: INVESTMENT_HOLDINGS TABLE (Section 3.3)
-- =============================================================================
-- Per-account, per-date snapshot of investment positions.

CREATE TABLE investment_holdings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    asset_name TEXT,
    asset_type investment_asset_type NOT NULL,
    quantity NUMERIC(15,6) NOT NULL,          -- 6 decimals for fractional/crypto
    cost_basis NUMERIC(15,2),
    currency TEXT NOT NULL,                   -- ISO 4217
    as_of_date DATE NOT NULL,
    source balance_snapshot_source NOT NULL DEFAULT 'manual',
    valuation_source valuation_source NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_inv_holdings_user ON investment_holdings(user_id);
CREATE INDEX idx_inv_holdings_account ON investment_holdings(account_id);
CREATE INDEX idx_inv_holdings_symbol ON investment_holdings(symbol);
CREATE INDEX idx_inv_holdings_as_of ON investment_holdings(account_id, as_of_date);

-- =============================================================================
-- F2.1.2: INVESTMENT_TRANSACTIONS TABLE (Section 3.4)
-- =============================================================================
-- Tracks buy/sell/corporate-action events for investment accounts.
-- Partial unique on external_id for idempotent imports.

CREATE TABLE investment_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    transaction_type investment_transaction_type NOT NULL,
    quantity NUMERIC(15,6) NOT NULL,
    price_per_unit NUMERIC(15,6) NOT NULL,
    total_amount NUMERIC(15,2) NOT NULL,
    currency TEXT NOT NULL,                   -- ISO 4217
    occurred_at TIMESTAMPTZ NOT NULL,
    lot_id TEXT,                              -- post-MVP: tax lot tracking
    source transaction_source NOT NULL DEFAULT 'manual',
    external_id TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Partial unique for idempotent imports
CREATE UNIQUE INDEX uq_inv_tx_account_external_id
    ON investment_transactions(account_id, external_id)
    WHERE external_id IS NOT NULL;

-- Indexes
CREATE INDEX idx_inv_tx_user ON investment_transactions(user_id);
CREATE INDEX idx_inv_tx_account_occurred ON investment_transactions(account_id, occurred_at);
CREATE INDEX idx_inv_tx_symbol ON investment_transactions(symbol);

-- =============================================================================
-- F2.1.3: EXCHANGE_RATES TABLE (Section 3.5)
-- =============================================================================
-- Historical currency exchange rates, one per pair per date.
-- Invariant F-10: historical net worth always uses rate from snapshot date.

CREATE TABLE exchange_rates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate NUMERIC(15,8) NOT NULL,
    rate_date DATE NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Invariant F-10: one rate per currency pair per date
    CONSTRAINT uq_exchange_rates_pair_date UNIQUE (base_currency, quote_currency, rate_date)
);

-- Indexes
CREATE INDEX idx_exchange_rates_date ON exchange_rates(rate_date);

-- =============================================================================
-- F2.1.4: MARKET_PRICES CACHE TABLE (Section 4.6)
-- =============================================================================
-- Derived cache — purgeable at any time.
-- Manual entry for MVP; API fetch post-MVP.

CREATE TABLE market_prices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    price NUMERIC(15,4) NOT NULL,
    currency TEXT NOT NULL,
    price_date DATE NOT NULL,
    source TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One price per symbol per date per source
    CONSTRAINT uq_market_prices_symbol_date_source UNIQUE (symbol, price_date, source)
);

-- Indexes
CREATE INDEX idx_market_prices_symbol ON market_prices(symbol);
CREATE INDEX idx_market_prices_date ON market_prices(price_date);

-- =============================================================================
-- F2.3.1: FINANCE_DAILY_ROLLUPS TABLE (Section 4.8)
-- =============================================================================
-- Refreshed on transaction insert/update (event-driven).
-- Derived layer — purgeable and recomputable (D-02).

CREATE TABLE finance_daily_rollups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    net_worth NUMERIC(15,2),
    liquid_net_worth NUMERIC(15,2),
    total_assets NUMERIC(15,2),
    total_liabilities NUMERIC(15,2),
    daily_income NUMERIC(15,2),
    daily_expenses NUMERIC(15,2),
    daily_net_cashflow NUMERIC(15,2),
    investment_value NUMERIC(15,2),

    -- One rollup per user per date
    CONSTRAINT uq_fin_daily_rollup_user_date UNIQUE (user_id, date)
);

-- Indexes
CREATE INDEX idx_fin_daily_rollup_date ON finance_daily_rollups(date);

-- =============================================================================
-- F2.3.2: FINANCE_WEEKLY_ROLLUPS TABLE (Section 4.8)
-- =============================================================================
-- Refreshed nightly. Derived layer (D-02).

CREATE TABLE finance_weekly_rollups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    total_income NUMERIC(15,2),
    total_expenses NUMERIC(15,2),
    net_cashflow NUMERIC(15,2),
    savings_rate NUMERIC(7,4),
    top_expense_categories JSONB,
    category_variance_flags JSONB,
    net_worth_start NUMERIC(15,2),
    net_worth_end NUMERIC(15,2),
    net_worth_delta NUMERIC(15,2),

    -- One rollup per user per week
    CONSTRAINT uq_fin_weekly_rollup_user_week UNIQUE (user_id, week_start_date)
);

-- =============================================================================
-- F2.3.3: FINANCE_MONTHLY_ROLLUPS TABLE (Section 4.8)
-- =============================================================================
-- Refreshed nightly. Derived layer (D-02).

CREATE TABLE finance_monthly_rollups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month DATE NOT NULL,
    net_worth_start NUMERIC(15,2),
    net_worth_end NUMERIC(15,2),
    net_worth_change NUMERIC(15,2),
    total_income NUMERIC(15,2),
    total_expenses NUMERIC(15,2),
    savings_rate NUMERIC(7,4),
    top_expense_categories JSONB,
    investment_return NUMERIC(15,2),
    goal_contributions JSONB,

    -- One rollup per user per month
    CONSTRAINT uq_fin_monthly_rollup_user_month UNIQUE (user_id, month)
);

-- =============================================================================
-- F2.3.4: PORTFOLIO_ROLLUPS TABLE (Section 4.8)
-- =============================================================================
-- Per-account investment performance rollups. Refreshed nightly.
-- Derived layer (D-02).

CREATE TABLE portfolio_rollups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_date DATE NOT NULL,
    period_type portfolio_rollup_period_type NOT NULL,
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    total_value NUMERIC(15,2),
    total_cost_basis NUMERIC(15,2),
    unrealized_gain NUMERIC(15,2),
    realized_gain_period NUMERIC(15,2),
    dividend_income_period NUMERIC(15,2),
    deposits_period NUMERIC(15,2),
    withdrawals_period NUMERIC(15,2),
    market_movement NUMERIC(15,2),          -- total_value change minus deposits plus withdrawals
    concentration_top_holding JSONB,

    -- One rollup per user per date per period type per account
    CONSTRAINT uq_portfolio_rollup_user_date_type_account
        UNIQUE (user_id, period_date, period_type, account_id)
);

-- Indexes
CREATE INDEX idx_portfolio_rollup_account ON portfolio_rollups(account_id);
CREATE INDEX idx_portfolio_rollup_period ON portfolio_rollups(period_date, period_type);

-- =============================================================================
-- F2.4.1: FINANCE_ALERTS TABLE (Section 5.1)
-- =============================================================================
-- Stateful projection of Derived signals — NOT source of truth (F-15).
-- Invariant F-14: dedup via dedup_key before upsert.

CREATE TABLE finance_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type alert_type NOT NULL,
    severity alert_severity NOT NULL,
    status alert_status NOT NULL DEFAULT 'active',
    entity_refs JSONB NOT NULL DEFAULT '{}',   -- { account_id?, transaction_id?, goal_id?, category_id?, obligation_id? }
    dedup_key TEXT NOT NULL,
    first_detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    snoozed_until TIMESTAMPTZ,
    dismissed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    explanation JSONB,                         -- DerivedExplanation snapshot
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Invariant F-14: unique dedup_key per user prevents duplicate alerts
    CONSTRAINT uq_finance_alerts_dedup UNIQUE (user_id, dedup_key)
);

COMMENT ON COLUMN finance_alerts.entity_refs IS 'References: { account_id?, transaction_id?, goal_id?, category_id?, obligation_id? }';
COMMENT ON COLUMN finance_alerts.explanation IS 'DerivedExplanation snapshot.';

-- Indexes
CREATE INDEX idx_finance_alerts_user_status ON finance_alerts(user_id, status);
CREATE INDEX idx_finance_alerts_type ON finance_alerts(alert_type);
CREATE INDEX idx_finance_alerts_severity ON finance_alerts(severity);
CREATE INDEX idx_finance_alerts_snoozed ON finance_alerts(snoozed_until)
    WHERE snoozed_until IS NOT NULL;

-- updated_at trigger
CREATE TRIGGER trg_finance_alerts_updated_at
    BEFORE UPDATE ON finance_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- F2.6.1: OBLIGATION_NODES COMPANION TABLE (Obligations Addendum Section 2)
-- =============================================================================
-- Core entity — durable, user-owned recurring financial commitments.
-- 1:1 with nodes table (node type 'obligation').
-- Invariant F-17: amount_model consistency (CHECK).
-- Invariant F-18: status lifecycle — cancelled requires ended_at (CHECK).
-- Invariant F-19: next_expected_date is CACHED DERIVED (S-01).

CREATE TABLE obligation_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    obligation_type obligation_type NOT NULL,
    recurrence_rule TEXT NOT NULL,
    amount_model amount_model NOT NULL,

    -- Invariant F-17: fixed → expected_amount required, ranges null;
    -- variable/seasonal → ranges required
    expected_amount NUMERIC(15,2),
    amount_range_low NUMERIC(15,2),
    amount_range_high NUMERIC(15,2),

    currency TEXT NOT NULL,                   -- ISO 4217
    account_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    counterparty_entity_id UUID,              -- FK deferred to F3 (counterparty_entities)
    category_id UUID REFERENCES financial_categories(id) ON DELETE SET NULL,
    billing_anchor SMALLINT,                  -- Typical day-of-month hint. Not source of truth.

    -- Invariant F-19 + S-01: CACHED DERIVED from recurrence_rule + last obligation_event
    next_expected_date DATE,

    status obligation_status NOT NULL DEFAULT 'active',
    autopay BOOLEAN NOT NULL DEFAULT false,
    origin obligation_origin NOT NULL,
    confidence FLOAT,                         -- Detection confidence at creation. NULL for manual.
    started_at DATE,
    ended_at DATE,
    cancellation_url TEXT,
    notes TEXT,

    -- Invariant F-17: Amount model consistency
    CONSTRAINT obligation_amount_model_consistency CHECK (
        (amount_model = 'fixed' AND expected_amount IS NOT NULL
         AND amount_range_low IS NULL AND amount_range_high IS NULL)
        OR
        (amount_model IN ('variable', 'seasonal')
         AND amount_range_low IS NOT NULL AND amount_range_high IS NOT NULL)
    ),

    -- Invariant F-18: Status lifecycle
    CONSTRAINT obligation_status_lifecycle CHECK (
        (status = 'cancelled' AND ended_at IS NOT NULL)
        OR (status = 'active' AND ended_at IS NULL)
        OR (status = 'paused')
    )
);

COMMENT ON COLUMN obligation_nodes.next_expected_date IS 'CACHED DERIVED: Computed from recurrence_rule + last obligation_event. Invariants S-01, F-19.';
COMMENT ON COLUMN obligation_nodes.counterparty_entity_id IS 'FK deferred to F3 (counterparty_entities).';
COMMENT ON COLUMN obligation_nodes.billing_anchor IS 'Typical day-of-month hint. Not source of truth.';
COMMENT ON COLUMN obligation_nodes.confidence IS 'Detection confidence at creation. NULL for manual.';

-- Indexes
CREATE INDEX idx_obligation_nodes_status ON obligation_nodes(status);
CREATE INDEX idx_obligation_nodes_account ON obligation_nodes(account_id);
CREATE INDEX idx_obligation_nodes_category ON obligation_nodes(category_id)
    WHERE category_id IS NOT NULL;
CREATE INDEX idx_obligation_nodes_next_date ON obligation_nodes(next_expected_date)
    WHERE next_expected_date IS NOT NULL;

-- =============================================================================
-- F2.6.2: OBLIGATION_BREAKDOWNS TABLE (Obligations Addendum Section 2)
-- =============================================================================
-- Sub-components of obligations (e.g. base charge, usage, taxes).
-- Versioned via effective_from/effective_to — never mutated for rate changes.
-- Invariant F-20: percentage model → percentage_value required, expected_amount null.
-- Invariant F-21: partial unique on (obligation_id, normalized_name) WHERE effective_to IS NULL.
-- Invariant F-22: deprecated status requires effective_to set.

CREATE TABLE obligation_breakdowns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    obligation_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    component_type breakdown_component_type NOT NULL,
    amount_model breakdown_amount_model NOT NULL,

    -- Invariant F-20: percentage → percentage_value non-null, expected_amount null; others inverse
    expected_amount NUMERIC(15,2),
    amount_range_low NUMERIC(15,2),
    amount_range_high NUMERIC(15,2),
    percentage_value NUMERIC(7,4),            -- For percentage-based: the rate (e.g. 0.0825 for 8.25%)

    match_keywords TEXT[],                    -- Hints for auto-matching transaction line items
    effective_from DATE NOT NULL,
    effective_to DATE,                        -- When superseded. NULL = current version.
    status breakdown_status NOT NULL DEFAULT 'active',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Invariant F-20: Breakdown amount model consistency
    CONSTRAINT breakdown_amount_model_consistency CHECK (
        (amount_model = 'percentage' AND percentage_value IS NOT NULL
         AND expected_amount IS NULL)
        OR
        (amount_model IN ('fixed', 'variable', 'seasonal')
         AND percentage_value IS NULL)
    ),

    -- Invariant F-22: deprecated status requires effective_to
    CONSTRAINT breakdown_deprecated_has_end_date CHECK (
        (status = 'deprecated' AND effective_to IS NOT NULL)
        OR (status = 'active')
    )
);

COMMENT ON COLUMN obligation_breakdowns.percentage_value IS 'For percentage-based: the rate (e.g. 0.0825 for 8.25%). NULL for non-percentage.';
COMMENT ON COLUMN obligation_breakdowns.effective_to IS 'When superseded. NULL = current version.';

-- Invariant F-21: One active version per (obligation_id, normalized_name)
CREATE UNIQUE INDEX uq_breakdown_active_version
    ON obligation_breakdowns(obligation_id, normalized_name)
    WHERE effective_to IS NULL;

-- Section 7: Obligation breakdown indexes
CREATE INDEX idx_breakdown_obligation ON obligation_breakdowns(obligation_id);
CREATE INDEX idx_breakdown_component_type ON obligation_breakdowns(component_type);
CREATE INDEX idx_breakdown_effective_range ON obligation_breakdowns(effective_from, effective_to);

-- updated_at trigger
CREATE TRIGGER trg_obligation_breakdowns_updated_at
    BEFORE UPDATE ON obligation_breakdowns
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- F2.6.3: UPDATE EDGE TYPE-PAIR CONSTRAINT TRIGGER (Invariant G-01)
-- =============================================================================
-- Add obligation_charges_account and obligation_impacts_goal validation.
-- Also add obligation semantic_reference pairs (F2.6.4).

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
        -- F2.6.3: obligation_charges_account (Obligations Addendum Section 2)
        WHEN 'obligation_charges_account' THEN
            valid := (source_type = 'obligation' AND target_type = 'account');
        -- F2.6.3: obligation_impacts_goal (Obligations Addendum Section 2)
        WHEN 'obligation_impacts_goal' THEN
            valid := (source_type = 'obligation' AND target_type = 'goal');
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
            -- F2.6.4: obligation <-> memory (Obligations Addendum Section 2)
            ELSIF (source_type = 'obligation' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'obligation') THEN
                valid := TRUE;
            -- F2.6.4: obligation <-> kb_entry (Obligations Addendum Section 2)
            ELSIF (source_type = 'obligation' AND target_type = 'kb_entry')
               OR (source_type = 'kb_entry' AND target_type = 'obligation') THEN
                valid := TRUE;
            -- F2.6.4: obligation <-> obligation (Obligations Addendum Section 2)
            ELSIF source_type = 'obligation' AND target_type = 'obligation' THEN
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
