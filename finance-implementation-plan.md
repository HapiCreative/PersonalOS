# Personal OS — Finance Module Implementation Plan

**Canonical Reference:** Finance Module Design Document Rev 3 + Obligations Addendum (Rev 4)
**Architecture Baseline:** Personal OS Architecture v6
**Date:** April 2026

-----

## Guiding Principles

1. **Finance extends existing workflows** — no parallel structures for Today Mode, reviews, or AI modes. Finance earns attention through existing channels.
1. **The graph is for meaning. Tables are for behavior and time.** — Accounts and obligations are Core nodes. Transactions are Temporal rows. Never graph edges on transactions.
1. **Manual-first data ingestion** — manual entry + CSV import. API sync (Plaid/SnapTrade) is post-MVP and additive.
1. **Each phase is shippable** — stop after any phase and have a working, useful system.
1. **Invariants are non-negotiable** — enforce from the phase they’re introduced. No deferred validation.
1. **Design doc is the source of truth** — every implementation decision traces to a section in the finance design doc or v6 architecture. If it’s not in the doc, it doesn’t get built.

-----

## Phase Map

|Phase|Name                             |Duration|Delivers                                                                                                                                                                     |
|-----|---------------------------------|--------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|F1   |Foundation + Capture             |2 weeks |Accounts, transactions, balance snapshots, CSV import, basic views                                                                                                           |
|F2   |Intelligence + Decision Surfaces |2 weeks |Net worth, cashflow, spending analytics, investment holdings, rollups, Alerts Engine (rule-based), obligation schema + manual creation + rule-based obligation alerts        |
|F3   |Behavioral Integration + Patterns|2 weeks |Today Mode, reviews, AI modes, obligation events + matching + seasonal intelligence, counterparty normalization, recurring patterns, pattern-based alerts, forecasting engine|
|F4   |Advanced                         |Post-MVP|API sync, cross-domain intelligence, lot tracking, behavioral finance, alert personalization                                                                                 |

This mirrors the roadmap in Section 8 of the finance design doc. Each phase below breaks into concrete implementation tasks.

-----

-----

# Phase F1: Foundation + Capture

**Design Doc Reference:** Section 8.1
**Duration:** 2 weeks
**Prerequisite:** Main OS graph (nodes, edges, users) + FastAPI scaffold + React shell running

> *“Without a trustworthy data model, later intelligence will be noisy and untrustworthy.”*

-----

## F1.1 — Core Schema

### F1.1.1 Account Nodes

**Ref:** Section 2.1

- Add `account` to `nodes.type` ENUM
- Create `account_nodes` companion table:

```
account_nodes (
  node_id       UUID PK FK → nodes,
  account_type  ENUM (checking, savings, credit_card, brokerage, crypto_wallet, cash, loan, mortgage, other),
  institution   TEXT NULL,
  currency      TEXT NOT NULL,          -- ISO 4217
  account_number_masked TEXT NULL,      -- last 4 digits only
  is_active     BOOLEAN DEFAULT true,
  notes         TEXT NULL
)
```

### F1.1.2 Goal Nodes Extension

**Ref:** Section 2.2

- Add three nullable fields + discriminator to existing `goal_nodes`:

```sql
ALTER TABLE goal_nodes ADD COLUMN goal_type ENUM DEFAULT 'general';  -- general | financial
ALTER TABLE goal_nodes ADD COLUMN target_amount NUMERIC(15,2) NULL;
ALTER TABLE goal_nodes ADD COLUMN current_amount NUMERIC(15,2) NULL; -- CACHED DERIVED (S-01)
ALTER TABLE goal_nodes ADD COLUMN currency TEXT NULL;                -- ISO 4217
```

- Application-layer enforcement of **F-03**: financial goals require non-null target_amount + currency; general goals require all three financial fields null.

### F1.1.3 Goal Allocations

**Ref:** Section 2.6

```
goal_allocations (
  id               UUID PK,
  goal_id          UUID FK → nodes,
  account_id       UUID FK → nodes,
  allocation_type  ENUM (percentage, fixed),
  value            NUMERIC(15,4),
  created_at       TIMESTAMPTZ,
  updated_at       TIMESTAMPTZ,
  UNIQUE(goal_id, account_id)
)
```

- Enforce **F-13**: for percentage allocations, SUM of values for a single account across all goals ≤ 1.0.
- Enforce **F-06**: no `funding_account_ids` arrays anywhere. Relationships are edges + allocations only.

### F1.1.4 Edge Relation: account_funds_goal

**Ref:** Section 2.3

- Add `account_funds_goal` to edge `relation_type` ENUM
- Add type-pair constraint: `account → goal` only
- Register in both application-layer validation and database trigger (G-01)

### F1.1.5 Financial Categories

**Ref:** Section 2.5

```
financial_categories (
  id          UUID PK,
  user_id     UUID FK → users,
  name        TEXT,
  parent_id   UUID NULL FK → financial_categories,
  icon        TEXT NULL,
  is_system   BOOLEAN DEFAULT false,
  sort_order  INTEGER DEFAULT 0,
  created_at  TIMESTAMPTZ,
  UNIQUE(user_id, name, parent_id)
)
```

- Seed system defaults on user creation: Groceries, Rent/Mortgage, Utilities, Dining, Transportation, Entertainment, Healthcare, Insurance, Subscriptions, Personal Care, Education, Gifts/Donations, Income, Investments, Fees, Other.
- **F-12**: category deletion blocked if transactions reference it.

### Acceptance Criteria — F1.1

- [ ] Account nodes created and visible in graph search
- [ ] Financial goals enforce F-03 field consistency
- [ ] Goal allocations enforce uniqueness and F-13 bounds
- [ ] `account_funds_goal` edges work with type-pair validation
- [ ] Categories seeded for new users; hierarchical parent_id works
- [ ] Category deletion blocked by referential integrity

-----

## F1.2 — Temporal: Transactions

### F1.2.1 Financial Transactions Table

**Ref:** Section 3.1

```
financial_transactions (
  id                    UUID PK,
  user_id               UUID FK → users,
  account_id            UUID FK → nodes,
  transaction_type      ENUM (income, expense, transfer_in, transfer_out,
                              investment_buy, investment_sell, dividend,
                              interest, fee, refund, adjustment),
  status                ENUM DEFAULT 'posted' (pending, posted, settled),
  amount                NUMERIC(15,2) NOT NULL,         -- always positive (F-02)
  signed_amount         NUMERIC(15,2) GENERATED ALWAYS AS (...) STORED,
  currency              TEXT NOT NULL,
  category_id           UUID NULL FK → financial_categories,
  subcategory_id        UUID NULL FK → financial_categories,
  category_source       ENUM DEFAULT 'manual' (manual, system_suggested, imported),
  counterparty          TEXT NULL,
  counterparty_entity_id UUID NULL,                     -- FK deferred to F3
  description           TEXT NULL,
  occurred_at           TIMESTAMPTZ NOT NULL,
  posted_at             TIMESTAMPTZ NULL,
  source                ENUM (manual, csv_import, api_sync),
  external_id           TEXT NULL,
  transfer_group_id     UUID NULL,
  tags                  TEXT[] NULL,
  is_voided             BOOLEAN DEFAULT false,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
)
```

- **signed_amount generation rule** (Section 3.1):

```sql
GENERATED ALWAYS AS (
  amount * CASE
    WHEN transaction_type IN ('income','transfer_in','refund','investment_sell','dividend','interest')
    THEN 1 ELSE -1
  END
) STORED
```

- **Pending transactions generate signed_amount = 0.** The design doc specifies: “Only applied when status IN (posted, settled). Pending transactions generate signed_amount = 0.” Balance queries additionally filter by status (F-08), but the generated column itself must handle the pending case.
- **Indexes**: `(account_id, occurred_at)`, `(user_id, occurred_at)`, `(account_id, external_id) WHERE external_id IS NOT NULL`, `(transfer_group_id) WHERE transfer_group_id IS NOT NULL`, `(category_id)`, `(status)`
- **Transfer integrity (F-05)**: exactly 2 records per `transfer_group_id` — 1 `transfer_out` + 1 `transfer_in`. Enforce at application layer on creation. Cleanup flags orphans.

### F1.2.2 Balance Snapshots Table

**Ref:** Section 3.2

```
balance_snapshots (
  id              UUID PK,
  user_id         UUID FK → users,
  account_id      UUID FK → nodes,
  balance         NUMERIC(15,2),
  currency        TEXT,
  snapshot_date   DATE,
  source          ENUM (manual, csv_import, api_sync, computed),
  is_reconciled   BOOLEAN DEFAULT false,
  reconciled_at   TIMESTAMPTZ NULL,
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(account_id, snapshot_date)
)
```

- **F-09**: computed balances never override reconciled snapshots. Application layer checks `is_reconciled` before upsert.

### Acceptance Criteria — F1.2

- [ ] Transactions store positive amounts only; signed_amount computed correctly
- [ ] Status lifecycle works: pending → posted → settled
- [ ] Balance snapshots enforce one-per-account-per-date
- [ ] Transfer creation produces exactly 2 paired records
- [ ] Voided transactions excluded from queries by default

-----

## F1.3 — Temporal: Financial Audit Trail

### F1.3.1 Transaction History Table

**Ref:** Section 3.6

```
financial_transaction_history (
  id               UUID PK,
  transaction_id   UUID FK → financial_transactions,
  version          INTEGER,
  snapshot         JSONB,
  change_type      ENUM (create, update, void),
  changed_by       UUID FK → users,
  changed_at       TIMESTAMPTZ DEFAULT now()
)
```

- **F-11**: every mutation to `financial_transactions` produces a history row. Append-only, never modified or deleted.
- On transaction create: insert history row with `change_type = create`, `version = 1`.
- On transaction update: insert history row with `change_type = update`, version incremented, full snapshot.
- On void: insert history row with `change_type = void`.

### Acceptance Criteria — F1.3

- [ ] Every transaction create/update/void produces a history row
- [ ] History rows are append-only, no updates or deletes
- [ ] Full transaction state captured in JSONB snapshot

-----

## F1.4 — Behavioral: Capture Workflows

### F1.4.1 Manual Entry Form

**Ref:** Section 5.2

- Quick-add form: account, amount, type, category (from `financial_categories` dropdown with hierarchy), date
- Defaults: most recently used account, date = today, status = posted
- On save: create transaction + audit history row, trigger async balance recomputation

### F1.4.2 CSV Import

**Ref:** Section 5.2

- Upload CSV → column mapping UI
- Save mapping per account for future imports
- Dedup via `UNIQUE(account_id, external_id)` — skip or flag duplicates
- Preview before commit with error/duplicate highlighting
- Bulk insert on confirm
- Auto-generate `balance_snapshots` if balance column present in CSV

### F1.4.3 Balance Snapshot Workflow

**Ref:** Section 5.3

- Manual: user enters current balance for an account (account, balance, date). Optional reconciliation checkbox.
- Balance authority rule enforced: reconciled snapshots are authoritative.

### Acceptance Criteria — F1.4

- [ ] Manual transaction entry with smart defaults (last account, today’s date)
- [ ] CSV import with column mapping, saved mappings, dedup, preview
- [ ] Balance snapshots created manually with optional reconciliation
- [ ] Audit trail records generated for all transaction mutations

-----

## F1.5 — Frontend: Basic Finance Views

### F1.5.1 Navigation

- Add `$` icon to rail nav for Finance section
- Finance module uses standard list/detail layout

### F1.5.2 Views

- **Accounts list**: name, type, institution, current balance, active/inactive badge
- **Account detail**: metadata + transaction list filtered to that account + balance history
- **Transactions list**: filterable by account, date range, type, category, status, amount range
- **Transaction detail sheet**: all fields, edit capability, audit history link
- **Category management**: CRUD for user categories, hierarchy display

### Acceptance Criteria — F1.5

- [ ] Finance section accessible from rail nav
- [ ] Account list shows all accounts with current balance
- [ ] Transaction list supports filtering and sorting
- [ ] Category picker shows hierarchical categories

-----

-----

# Phase F2: Intelligence + Decision Surfaces

**Design Doc Reference:** Section 8.2
**Duration:** 2 weeks
**Prerequisite:** F1 complete

> *“This is where the module becomes Personal OS-native. Intelligence and alerts transform it from a dashboard into a behavior engine.”*

-----

## F2.1 — Temporal: Investment Tables

### F2.1.1 Investment Holdings

**Ref:** Section 3.3

```
investment_holdings (
  id               UUID PK,
  user_id          UUID FK → users,
  account_id       UUID FK → nodes,
  symbol           TEXT,
  asset_name       TEXT NULL,
  asset_type       ENUM (stock, etf, mutual_fund, bond, crypto, option, other),
  quantity         NUMERIC(15,6),    -- 6 decimals for fractional/crypto
  cost_basis       NUMERIC(15,2) NULL,
  currency         TEXT,
  as_of_date       DATE,
  source           ENUM (manual, csv_import, api_sync, computed),
  valuation_source ENUM (market_api, manual, computed),
  created_at       TIMESTAMPTZ DEFAULT now()
)
```

### F2.1.2 Investment Transactions

**Ref:** Section 3.4

```
investment_transactions (
  id               UUID PK,
  user_id          UUID FK → users,
  account_id       UUID FK → nodes,
  symbol           TEXT,
  transaction_type ENUM (buy, sell, dividend_reinvest, split, merger, spinoff),
  quantity         NUMERIC(15,6),
  price_per_unit   NUMERIC(15,6),
  total_amount     NUMERIC(15,2),
  currency         TEXT,
  occurred_at      TIMESTAMPTZ,
  lot_id           TEXT NULL,           -- post-MVP: tax lot tracking
  source           ENUM (manual, csv_import, api_sync),
  external_id      TEXT NULL,
  notes            TEXT NULL,
  created_at       TIMESTAMPTZ DEFAULT now(),
  UNIQUE(account_id, external_id) WHERE external_id IS NOT NULL
)
```

### F2.1.3 Exchange Rates

**Ref:** Section 3.5

```
exchange_rates (
  id              UUID PK,
  base_currency   TEXT,
  quote_currency  TEXT,
  rate            NUMERIC(15,8),
  rate_date       DATE,
  source          TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(base_currency, quote_currency, rate_date)
)
```

- **F-10**: historical net worth always uses rate from snapshot date, never current date.

### F2.1.4 Market Prices Cache

**Ref:** Section 4.6

```
market_prices (
  symbol       TEXT,
  price        NUMERIC(15,4),
  currency     TEXT,
  price_date   DATE,
  source       TEXT,
  fetched_at   TIMESTAMPTZ,
  UNIQUE(symbol, price_date, source)
)
```

- Derived cache — purgeable at any time. Manual entry for MVP; API fetch post-MVP.

### Acceptance Criteria — F2.1

- [ ] Holdings snapshots stored per account per date
- [ ] Investment transactions tracked with corporate action support (split, merger)
- [ ] Exchange rates stored historically per currency pair per date
- [ ] Market prices cached with manual entry support

-----

## F2.2 — Derived: Core Financial Intelligence

### F2.2.1 Net Worth Engine

**Ref:** Section 4.1

- Compute net worth at any date: sum all account balances (most recent snapshot on or before target date)
- Liabilities: loan, mortgage, credit_card (balance subtracted)
- Assets: all others (balance added)
- Multi-currency: convert to user’s base currency using exchange_rates at snapshot date (F-10)
- **Liquid net worth**: exclude illiquid assets (mortgage equity, retirement, long-term locked). Determined by account_type + asset_type within holdings.

### F2.2.2 Cashflow Analytics

**Ref:** Section 4.2

- `monthly_income`: SUM(signed_amount) WHERE type IN (income, dividend, interest, refund) AND status IN (posted, settled)
- `monthly_expenses`: SUM(ABS(signed_amount)) WHERE type IN (expense, fee) AND status IN (posted, settled)
- `net_cashflow`: income - expenses
- `savings_rate`: net_cashflow / monthly_income
- `burn_rate`: monthly_expenses / 30
- **F-07**: transfers and investment transactions excluded from cashflow.

### F2.2.3 Spending Intelligence

**Ref:** Section 4.3

- **Category breakdown**: group expenses by `category_id` with hierarchy rollup per period (week, month, quarter)
- **Trend detection**: current month category spend vs rolling 3-month average. Flag categories exceeding 1.5× average.
- **Anomaly detection**: individual transactions > 3× category median. Uses DerivedExplanation schema (D-01).
- **Merchant concentration** (Rev3): share of spend concentrated in a single counterparty. Flags when a single merchant exceeds configurable threshold (default: 30% of category spend). Until counterparty_entities activated in F3, uses raw counterparty strings with fuzzy matching.
- **Spend creep** (Rev3): slow sustained increase in a category over multiple periods. Detected by comparing rolling 3-month averages across consecutive windows. Surfaced in Monthly Review and Improve mode.
- **Leakage candidates** (Rev3): low-value recurring or repeated discretionary spend the user may not be consciously choosing. Until recurring_patterns activated in F3, uses simple frequency-based heuristics. Surfaced in Improve mode.

Note: merchant concentration, spend creep, and leakage are standalone Derived metrics that also feed the Alerts Engine as signal sources in F3. They should be computed and queryable independently of alerts.

### F2.2.4 Financial Goal Progress

**Ref:** Section 4.4

- `current_amount` = SUM(account_balance × allocation) for all accounts linked via `goal_allocations`
- `progress_pct` = (current_amount / target_amount) × 100
- `projected_completion` = linear projection from contribution rate over last 90 days
- `monthly_contribution_needed` = (target_amount - current_amount) / months_until_deadline
- Background job updates `goal_nodes.current_amount` (cached Derived field).

### F2.2.5 Investment Performance

**Ref:** Section 4.5

- `total_value`: SUM(quantity × current_price) per account
- `total_cost_basis`: SUM(cost_basis) across holdings
- `unrealized_gain`: total_value - total_cost_basis
- `simple_return`: (current_value - total_invested + dividends) / total_invested
- `dividend_income`: SUM from dividend transactions per period
- `realized_gain`: from sell investment_transactions vs cost basis. **Note:** uses lot tracking when available (post-MVP, F4.5). Until then, uses average cost basis.

### Acceptance Criteria — F2.2

- [ ] Net worth computed correctly with liability/asset classification
- [ ] Liquid net worth toggleable
- [ ] Cashflow excludes transfers and investment types (F-07)
- [ ] Category breakdown with hierarchy rollup works
- [ ] Spending anomalies detected and explained via DerivedExplanation
- [ ] Merchant concentration computed (fuzzy matching pre-F3)
- [ ] Spend creep detected across consecutive periods
- [ ] Leakage candidates surfaced (frequency heuristics pre-F3)
- [ ] Financial goal progress computed from allocations, not raw balances

-----

## F2.3 — Derived: Rollup Tables

**Ref:** Section 4.8

### F2.3.1 Finance Daily Rollups

`finance_daily_rollups`: user_id, date, net_worth, liquid_net_worth, total_assets, total_liabilities, daily_income, daily_expenses, daily_net_cashflow, investment_value. Refreshed on transaction insert/update (event-driven).

### F2.3.2 Finance Weekly Rollups

`finance_weekly_rollups`: user_id, week_start_date, week_end_date, total_income, total_expenses, net_cashflow, savings_rate, top_expense_categories (JSONB), category_variance_flags (JSONB), net_worth_start, net_worth_end, net_worth_delta. Refreshed nightly.

### F2.3.3 Finance Monthly Rollups

`finance_monthly_rollups`: user_id, month, net_worth_start, net_worth_end, net_worth_change, total_income, total_expenses, savings_rate, top_expense_categories (JSONB), investment_return, goal_contributions (JSONB). Refreshed nightly.

### F2.3.4 Portfolio Rollups

`portfolio_rollups`: user_id, period_date, period_type (daily, monthly), account_id, total_value, total_cost_basis, unrealized_gain, realized_gain_period, dividend_income_period, deposits_period, withdrawals_period, market_movement (total_value change - deposits + withdrawals), concentration_top_holding (JSONB). Refreshed nightly.

### Acceptance Criteria — F2.3

- [ ] Daily rollups refresh on transaction events
- [ ] Weekly, monthly, portfolio rollups refresh nightly
- [ ] All rollups are Derived — purgeable and recomputable (D-02)

-----

## F2.4 — Behavioral: Alerts Engine (Rule-Based MVP)

**Ref:** Section 5.1

### F2.4.1 Finance Alerts Table

```
finance_alerts (
  id                UUID PK,
  user_id           UUID FK → users,
  alert_type        ENUM (see taxonomy below),
  severity          ENUM (high, medium, low),
  status            ENUM (active, dismissed, snoozed, resolved),
  entity_refs       JSONB,              -- { account_id?, transaction_id?, goal_id?, category_id? }
  dedup_key         TEXT,
  first_detected_at TIMESTAMPTZ,
  last_seen_at      TIMESTAMPTZ,
  snoozed_until     TIMESTAMPTZ NULL,
  dismissed_at      TIMESTAMPTZ NULL,
  resolved_at       TIMESTAMPTZ NULL,
  explanation       JSONB,              -- DerivedExplanation snapshot
  created_at        TIMESTAMPTZ DEFAULT now(),
  updated_at        TIMESTAMPTZ DEFAULT now()
)
```

- **F-14**: deduplicate via `dedup_key` before upsert. Duplicate signals update `last_seen_at`, not create new rows.
- **F-15**: this table is NOT source of truth — it’s a stateful projection of Derived signals.

### F2.4.2 Rule-Based Alert Types (MVP)

|Alert Type               |Trigger                                                               |Default Severity|
|-------------------------|----------------------------------------------------------------------|----------------|
|`low_cash_runway`        |Projected month-end cash < user-defined threshold                     |high            |
|`large_transaction`      |Transaction > 3× category median                                      |medium          |
|`uncategorized_aging`    |Uncategorized transactions older than 3 days                          |low             |
|`duplicate_import`       |Potential duplicate detected during import                            |medium          |
|`stale_pending`          |Pending transactions older than 7 days                                |low             |
|`goal_off_track`         |Financial goal projected to miss deadline at current contribution rate|high            |
|`unreconciled_divergence`|Computed balance diverges > 5% from last reconciled snapshot          |medium          |
|`broken_transfer`        |transfer_group_id with count ≠ 2                                      |medium          |

### F2.4.3 Detection Loop

- Behavioral background job runs on schedule (configurable, default: every 6 hours)
- Each detection function produces `DerivedAlertCandidate { type, severity, entity_refs, explanation, score, dedup_key }`
- Deduplicate → upsert into `finance_alerts`
- Auto-resolution: if candidate no longer produced, set status → resolved

### F2.4.4 Three-Tier Routing

|Severity|Routing                                        |Attention Budget                                   |
|--------|-----------------------------------------------|---------------------------------------------------|
|High    |Today Mode (via P4 goal nudges or P1 due tasks)|Subject to U-01: max 2 unsolicited items           |
|Medium  |Finance Review Queue (within Cleanup System)   |Surfaces during financial review or cleanup        |
|Low     |Finance module only (passive insight)          |Visible in finance section, no external competition|

### F2.4.5 Alert User Actions

- Dismiss: sets `dismissed_at`, stops resurfacing
- Snooze: sets `snoozed_until`, hides until date
- Resolve: explicit user closure

### Acceptance Criteria — F2.4

- [ ] All 8 rule-based alert types detecting correctly
- [ ] Dedup prevents duplicate alerts for same signal (F-14)
- [ ] Auto-resolution works when underlying condition clears
- [ ] Dismiss, snooze, resolve lifecycle works
- [ ] High-severity alerts route to Today Mode within attention budget

-----

## F2.5 — Frontend: Intelligence Views

### F2.5.1 Overview Screen

**Ref:** Section 6 (UX→System Mapping) + Section 7.1

Implementation should reference the UX→System Mapping table in design doc Section 6 for layer/data-source grounding of each screen block.

- **Hero**: net worth + trend chart with period switcher. Liquid net worth toggle. Period switcher changes both the chart and the narrative explanation below it.
- **Cashflow cards**: income, expenses, net cashflow, savings rate. Pending vs posted treatment. Forecast access link.
- **Insights panel**: active alerts with primary action + explanation. Decision surface, not decoration. Split descriptive metrics (“net worth is X”) from action metrics (“you need to move $350 this week”).

### F2.5.2 Account Detail Enhancements

**Ref:** Section 7.2

- **Account list**: show reconciliation state directly: current, stale, needs review, disconnected
- **Account detail**: balance history, pending transaction total, upcoming obligations (when obligations activate in F3)
- **Credit accounts**: show utilization and statement due context, not just balance
- **Brokerage accounts**: support liquid vs illiquid treatment where relevant to wider system net worth calculations

### F2.5.3 Transactions List Enhancements

**Ref:** Section 7.3

- State chips: pending, posted, settled, imported, suspicious, uncategorized
- Filters: account, category, merchant, status, tags, amount range, date range
- Bulk actions: categorize, ignore, merge duplicates, mark as transfer, mark recurring, fix broken imports

### F2.5.4 Holdings View

**Ref:** Section 7.4

- Portfolio composition per brokerage account
- Performance: market movement vs contributions (from portfolio_rollups)
- Concentration and diversification warnings when single holding or sector dominates
- Brokerage accounts should support liquid vs illiquid treatment

### F2.5.5 Financial Goal Progress

- Goal progress card: current_amount, target_amount, progress_pct, projected completion
- Actionable: transfer, adjust target, revise deadline

### F2.5.6 Graph Connections

**Ref:** Section 2.4 + Obligations Addendum Section 2.4

Verify all specified graph connections work in the UI (backlinks, context layer):

- Account → Financial Goal via account_funds_goal
- Goal → Task via goal_tracks_task
- Memory → Account via semantic_reference
- Source → Goal via source_supports_goal
- Source → Account via captured_for
- Journal → Account via journal_reflects_on

### Acceptance Criteria — F2.5

- [ ] Net worth chart with liquid toggle and period switching (chart + narrative update together)
- [ ] Cashflow cards with explanation text and pending/posted distinction
- [ ] Insights panel shows active alerts with actions
- [ ] Account list shows reconciliation state badges
- [ ] Credit accounts show utilization context
- [ ] Holdings view separates market movement from contributions
- [ ] Holdings view shows concentration warnings
- [ ] Goal progress shows computed data from allocations
- [ ] All graph connections from design doc Section 2.4 verified in context layer

-----

## F2.6 — Core: Obligation Nodes (Schema + Manual Creation)

**Ref:** Obligations Addendum Sections 1, 2, 5.1, 8.1

**Two-Stage Lifecycle** (Addendum Section 1.2): Stage 1 — Detection (Derived): recurring_patterns detects patterns from transaction history. Patterns with confidence > 0.7 become promotion candidates. Stage 2 — Promotion (Core): user confirms a detected pattern, or manually creates an obligation. Promotion Contract (v6 Section 5.8) applies — provenance edge back to originating pattern.

**Constraint 8**: Obligations are Core entities promoted from Derived patterns or manually created. They participate in the graph, link to accounts and goals, and drive Behavioral alerting. Transaction matching emits Temporal events; Derived recomputes from events. Derived never mutates Derived directly.

Per the Obligations Addendum roadmap, obligation_nodes, breakdowns, edge relations, and rule-based obligation alerts belong in Phase 2 (F2). Transaction matching, seasonal intelligence, and pattern-based alerts belong in Phase 3 (F3).

### F2.6.1 Obligation Node Type + Companion Table

- Add `obligation` to `nodes.type` ENUM

```
obligation_nodes (
  node_id                UUID PK FK → nodes,
  obligation_type        ENUM (subscription, utility, rent, loan, insurance, tax, membership, other),
  recurrence_rule        TEXT,
  amount_model           ENUM (fixed, variable, seasonal),
  expected_amount        NUMERIC(15,2) NULL,
  amount_range_low       NUMERIC(15,2) NULL,
  amount_range_high      NUMERIC(15,2) NULL,
  currency               TEXT,
  account_id             UUID FK → nodes,
  counterparty_entity_id UUID NULL,     -- FK deferred to F3
  category_id            UUID NULL FK → financial_categories,
  billing_anchor         SMALLINT NULL,
  next_expected_date     DATE NULL,     -- CACHED DERIVED (S-01, F-19)
  status                 ENUM (active, paused, cancelled),
  autopay                BOOLEAN DEFAULT false,
  origin                 ENUM (manual, detected),
  confidence             FLOAT NULL,
  started_at             DATE NULL,
  ended_at               DATE NULL,
  cancellation_url       TEXT NULL,
  notes                  TEXT NULL
)
```

- **F-17**: amount_model = fixed requires expected_amount non-null, range fields null. variable/seasonal requires range fields non-null.
- **F-18**: cancelled requires ended_at set. active requires ended_at null.
- **F-19**: next_expected_date is CACHED DERIVED from recurrence_rule + last obligation_event.

### F2.6.2 Obligation Breakdowns

```
obligation_breakdowns (
  id                UUID PK,
  obligation_id     UUID FK → nodes,
  name              TEXT,
  normalized_name   TEXT,
  component_type    ENUM (base, usage, tax, fee, discount, adjustment, other),
  amount_model      ENUM (fixed, variable, seasonal, percentage),
  expected_amount   NUMERIC(15,2) NULL,
  amount_range_low  NUMERIC(15,2) NULL,
  amount_range_high NUMERIC(15,2) NULL,
  percentage_value  NUMERIC(7,4) NULL,
  match_keywords    TEXT[] NULL,
  effective_from    DATE,
  effective_to      DATE NULL,
  status            ENUM (active, deprecated),
  sort_order        INTEGER DEFAULT 0,
  created_at        TIMESTAMPTZ,
  updated_at        TIMESTAMPTZ
)
```

- **F-20**: percentage model requires percentage_value non-null, expected_amount null. Others: inverse.
- **F-21**: partial unique index on `(obligation_id, normalized_name) WHERE effective_to IS NULL`.
- **F-22**: deprecated status requires effective_to set.

### F2.6.3 New Edge Relations

- `obligation_charges_account`: obligation → account
- `obligation_impacts_goal`: obligation → goal
- Both registered with type-pair constraints. G-02 compliance.

### F2.6.4 Semantic Reference Updates

- Add to allowed semantic_reference pairs: obligation ↔ memory, obligation ↔ kb_entry, obligation ↔ obligation

### F2.6.5 Indexes (Obligations)

**Ref:** Obligations Addendum Section 7

- `obligation_breakdowns(obligation_id)` — fetch all components
- `obligation_breakdowns(component_type)` — cross-obligation analytics
- `obligation_breakdowns(effective_from, effective_to)` — historical range queries
- Partial unique: `obligation_breakdowns(obligation_id, normalized_name) WHERE effective_to IS NULL` — enforces F-21

### F2.6.6 Rule-Based Obligation Alert Types

Added to the Alerts Engine (F2.4):

|Alert Type               |Trigger                                      |Default Severity              |Autopay Behavior                 |
|-------------------------|---------------------------------------------|------------------------------|---------------------------------|
|`upcoming_obligation`    |Due within dynamic lead_time, no match yet   |medium (high if autopay=false)|Suppressed to low if autopay=true|
|`missed_obligation`      |Past expected date, no matching transaction  |high                          |Deferred 5 days if autopay=true  |
|`obligation_amount_spike`|Matched txn exceeds expected/seasonal by >20%|medium                        |Same                             |
|`obligation_rate_change` |2+ consecutive months at new amount (±5%)    |low                           |Same                             |
|`obligation_expiring`    |Known end date within 14 days                |low                           |Same                             |

**Dynamic lead time** (Obligations Addendum Section 5.2):
`lead_time = base_lead_time × adjustments`. Base = 3 days. Adjustments: autopay=true → reduce to 1 day. Historical variance > 2 days → extend by variance. Account balance < expected amount → extend to 5 days (future). Clamped to [1, 7] days. Computed on each detection loop, never stored.

### F2.6.7 Manual Obligation Creation Form

- Create/edit obligation form: type, recurrence, amount model, expected amount/range, account, category, autopay, cancellation URL
- Breakdown editor: add/edit/version components
- Link to account and goal via edge UI

### Acceptance Criteria — F2.6

- [ ] Obligation nodes created and visible in graph
- [ ] Breakdowns support versioned components with rate change history
- [ ] Edge relations enforce correct type-pairs
- [ ] Amount model invariants validated (F-17, F-20)
- [ ] Status lifecycle invariants validated (F-18)
- [ ] Rule-based obligation alerts detecting (upcoming, missed, spike, rate change, expiring)
- [ ] Dynamic lead time calculation working
- [ ] Autopay-aware severity adjustment working
- [ ] All obligation-related indexes created
- [ ] Obligation graph connections verified: obligation → account (obligation_charges_account), obligation → goal (obligation_impacts_goal), memory ↔ obligation (semantic_reference), source → obligation (captured_for), journal → obligation (journal_reflects_on), obligation ↔ obligation (semantic_reference for bundles)

-----

-----

# Phase F3: Behavioral Integration + Patterns

**Design Doc Reference:** Section 8.3 + Obligations Addendum
**Duration:** 2 weeks
**Prerequisite:** F2 complete

> *“This creates durable differentiation versus standard finance dashboards.”*

-----

## F3.1 — Temporal: Obligation Events

**Ref:** Obligations Addendum Section 3.1 + Section 8.2 (“Finance Phase 3 Additions”)

Obligation schema was created in F2.6. This phase activates the Temporal event layer, transaction matching, and seasonal intelligence.

**Correct Data Flow** (Addendum Section 3.2 — critical architectural principle):

1. Transaction posts → Derived matching computes candidate match with weighted confidence score.
1. Match accepted → obligation_events row created (Temporal) with event_status=paid, transaction_id set, match_confidence stored.
1. Derived recomputation triggered → next_expected_date on obligation_nodes recalculated from recurrence_rule + latest obligation_event.
1. No match by expected date + lead_time → obligation_events row created with event_status=missed → Alerts Engine fires.

Derived never mutates Derived directly. Transaction matching emits Temporal events, and Derived recomputes from those events.

```
obligation_events (
  id                UUID PK,
  user_id           UUID FK → users,
  obligation_id     UUID FK → nodes,
  expected_for_date DATE,
  transaction_id    UUID NULL FK → financial_transactions,
  event_status      ENUM (paid, missed, upcoming, skipped),
  match_confidence  FLOAT NULL,
  occurred_at       TIMESTAMPTZ NULL,
  notes             TEXT NULL,
  created_at        TIMESTAMPTZ DEFAULT now()
)
```

- **F-25**: at most one terminal event (paid, missed, skipped) per obligation per expected_for_date.
- **F-26**: user_id must match owner_id of referenced obligation node.

**Indexes** (Obligations Addendum Section 7):

- `(obligation_id, expected_for_date)` — lookup and uniqueness enforcement
- `(user_id, expected_for_date)` — “what’s due this week” queries
- `(transaction_id) WHERE transaction_id IS NOT NULL` — reverse lookup from transaction

### Acceptance Criteria — F3.1

- [ ] Obligation events enforce one-per-date uniqueness (F-25)
- [ ] Ownership alignment validated (F-26)
- [ ] Events link to matched transactions when applicable
- [ ] All indexes created

-----

## F3.3 — Core: Counterparty Entities (Activated)

**Ref:** Section 2.7

```
counterparty_entities (
  id               UUID PK,
  user_id          UUID FK → users,
  canonical_name   TEXT,
  aliases          TEXT[],
  category_id      UUID NULL FK → financial_categories,
  merchant_type    ENUM NULL (retailer, employer, utility, subscription, government, transfer_target, other),
  is_subscription  BOOLEAN DEFAULT false,
  url              TEXT NULL,
  notes            TEXT NULL,
  created_at       TIMESTAMPTZ,
  updated_at       TIMESTAMPTZ,
  UNIQUE(user_id, canonical_name)
)
```

- Resolution flow: on transaction import/create, match raw counterparty string against aliases. If match found, set `counterparty_entity_id`. If no match, store raw string as-is. Behavioral job clusters similar strings and suggests new entities.
- Enable `counterparty_entity_id` FK on `financial_transactions` (was nullable/deferred).

### Acceptance Criteria — F3.3

- [ ] Counterparty entities created with alias matching
- [ ] Transactions auto-link to counterparty on import
- [ ] Default category auto-populated from counterparty when transaction has none
- [ ] Merge and rename counterparty entities updates all referenced transactions

-----

## F3.4 — Derived: Recurring Patterns

**Ref:** Section 4.7

```
recurring_patterns (
  id                     UUID PK,
  user_id                UUID FK → users,
  account_id             UUID FK → nodes,
  counterparty           TEXT NULL,
  counterparty_entity_id UUID NULL FK → counterparty_entities,
  pattern_type           ENUM (subscription, income, bill, transfer, other),
  category_id            UUID NULL FK → financial_categories,
  frequency              ENUM (weekly, biweekly, monthly, quarterly, annual, irregular),
  expected_amount        NUMERIC(15,2),
  amount_variance        NUMERIC(15,2) NULL,
  last_occurrence        TIMESTAMPTZ,
  next_expected          DATE NULL,
  confidence             FLOAT,
  status                 ENUM (active, paused, ended, user_confirmed, user_dismissed),
  transaction_ids        UUID[],
  computed_at            TIMESTAMPTZ
)
```

- **Detection algorithm**: group transactions by (account_id, counterparty/entity, approximate amount). For groups with 3+ occurrences, classify frequency from median interval. Compute confidence from interval regularity and amount consistency.
- **F-16**: confidence < 0.5 not surfaced. 0.5–0.7 surfaced as suggestions. > 0.7 auto-classified.
- **Two-stage lifecycle**: detected pattern with high confidence → user confirms → promotes to obligation_node (Core). Promotion Contract applies (v6 Section 5.8).

### Acceptance Criteria — F3.4

- [ ] Pattern detection runs and identifies recurring transactions
- [ ] Confidence thresholds respected (F-16)
- [ ] High-confidence patterns promotable to obligation nodes
- [ ] Promotion creates provenance edge back to originating pattern

-----

## F3.5 — Derived: Seasonal Intelligence

**Ref:** Obligations Addendum Section 4.1

```
obligation_seasonal_profiles (
  id                   UUID PK,
  obligation_id        UUID FK → nodes,
  breakdown_id         UUID NULL FK → obligation_breakdowns,
  period_type          ENUM DEFAULT 'month',
  period_value         SMALLINT,         -- 1–12 for month
  expected_amount      NUMERIC(15,2),
  p25_amount           NUMERIC(15,2) NULL,
  p75_amount           NUMERIC(15,2) NULL,
  sample_count         SMALLINT,
  last_sample_at       TIMESTAMPTZ NULL,
  confidence           FLOAT,
  is_seasonal          BOOLEAN,
  seasonality_strength FLOAT NULL,
  annual_median        NUMERIC(15,2),
  annual_p25           NUMERIC(15,2) NULL,
  annual_p75           NUMERIC(15,2) NULL,
  computed_at          TIMESTAMPTZ
)
```

- **F-23**: profiles with confidence < 0.5 excluded from anomaly detection and forecasting.
- **F-24**: is_seasonal requires 2+ consecutive periods with |seasonality_strength| > 0.5.
- **Rate change detection**: 2 consecutive months at new amount (±5%) → surface recommendation to update obligation.

**Confidence Calculation** (Obligations Addendum Section 4.2):

`confidence = w1 × min(sample_count / 6, 1.0) + w2 × variance_stability + w3 × recency_score`

Where w1=0.4, w2=0.35, w3=0.25. Variance stability = 1 - (coefficient of variation), clamped to [0,1]. Recency score decays from 1.0 based on months since last_sample_at (exponential, half-life = 12 months).

**Seasonality Detection Algorithm** (Obligations Addendum Section 4.3):

1. Collect matched transactions over past 24 months, weighted by recency (exponential decay, half-life = 12 months).
1. Compute annual baseline: weighted median, p25, p75.
1. Group by period. For each period with 2+ data points, compute weighted median and IQR.
1. Compute seasonality_strength per period: `(period_median - annual_median) / annual_IQR`.
1. Flag `is_seasonal = true` if any 2+ consecutive periods show `|seasonality_strength| > 0.5`.
1. Profiles with confidence < 0.5 are not used for alerting (consistent with F-16).

**Indexes** (Obligations Addendum Section 7):

- `(obligation_id, period_type, period_value)` — seasonal lookup
- `(obligation_id, breakdown_id)` — per-component profiles

**Downstream Consumers** (Addendum Section 4.5):

|Consumer          |Usage                                                                                   |
|------------------|----------------------------------------------------------------------------------------|
|Anomaly detection |Compare against seasonal profile instead of annual median. Eliminates false positives.  |
|Forecasting engine|Month-end cash forecast uses seasonal profiles for variable obligations.                |
|Alerts Engine     |Seasonally-aware alerting: “July electricity $230 exceeds typical July range $170–$200.”|
|Monthly Review    |“Heating costs entering seasonal peak. Expected +$60/month through February.”           |

### Acceptance Criteria — F3.5

- [ ] Seasonal profiles computed for variable/seasonal obligations
- [ ] Confidence thresholds enforced (F-23)
- [ ] Seasonality correctly requires consecutive deviation (F-24)
- [ ] Rate changes detected after 2 consecutive months
- [ ] Anomaly detection uses seasonal profiles when available (eliminating false positives)
- [ ] Forecasting engine consumes seasonal profiles for variable obligations

-----

## F3.6 — Derived: Transaction-to-Obligation Matching

**Ref:** Obligations Addendum Section 3.3

Weighted confidence scoring:

|Signal                    |Weight|
|--------------------------|------|
|counterparty_entity match |0.45  |
|amount within range       |0.20  |
|timing proximity (±5 days)|0.20  |
|category match            |0.10  |
|account match             |0.05  |

- Auto-link ≥ 0.7. Suggestion 0.4–0.7. Below 0.4: no match.
- Match accepted → obligation_event created (Temporal, event_status = paid)
- No match by expected date + lead_time → obligation_event created (event_status = missed) → Alerts Engine fires

### Acceptance Criteria — F3.6

- [ ] Matching runs on each posted transaction
- [ ] Confidence scores computed correctly from weighted signals
- [ ] Auto-link and suggestion thresholds working
- [ ] Missed obligations detected and alerted

-----

## F3.7 — Behavioral: Pattern-Based Alerts (Activated)

**Ref:** Section 5.1 pattern-based taxonomy + Obligations Addendum Section 5.1

New alert types added to Alerts Engine (note: rule-based obligation alerts already in F2.6):

|Alert Type                |Trigger                                                         |Default Severity|
|--------------------------|----------------------------------------------------------------|----------------|
|`subscription_detected`   |New recurring pattern with high confidence                      |low             |
|`spend_creep`             |Category spend increasing across consecutive periods            |medium          |
|`impulse_cluster`         |Cluster of unplanned discretionary transactions in short window |medium          |
|`income_irregularity`     |Expected income pattern missed or amount varies significantly   |high            |
|`missed_obligation`       |Expected recurring payment did not occur on schedule            |high            |
|`portfolio_drift`         |Asset concentration exceeds threshold                           |medium          |
|`obligation_creep`        |Total obligation spend increasing 3+ consecutive months         |medium          |
|`obligation_concentration`|Single provider >40% of total obligation spend                  |low             |
|`obligation_optimization` |Similar obligations at lower market rates (requires source data)|low             |

### Acceptance Criteria — F3.7

- [ ] All pattern-based alert types detecting correctly
- [ ] Obligation alerts route through existing three-tier model

-----

## F3.8 — Derived: Forecasting Engine

**Ref:** Section 4.10 + Section 8.3 (“Spending intelligence upgraded… forecasting engine”)

The design doc places the forecasting engine in Phase 3. All forecasts use DerivedExplanation schema. Forecasts are recomputable and never source of truth.

|Forecast                 |Definition                                                                                                |Inputs                                                   |UI Surface                                           |
|-------------------------|----------------------------------------------------------------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
|Month-end cash forecast  |Project ending balance using known recurring obligations, income events, and recent discretionary behavior|Transactions, recurring_patterns, balance_snapshots      |Overview insight panel, Today Mode (if risk detected)|
|Goal completion forecast |Estimate completion date using actual contribution trend, not aspirational target only                    |goal_allocations, balance_snapshots, contribution history|Goal detail, financial goal nudge                    |
|Burn rate forecast       |Estimate how long current liquid cash can support present spending patterns                               |Liquid net worth, monthly_expenses                       |Overview, Today Mode (if < 3 months runway)          |
|Contribution gap forecast|Monthly amount needed to recover an off-track goal                                                        |target_amount, current_amount, deadline                  |Goal detail, Monthly Review                          |

### Acceptance Criteria — F3.8

- [ ] Month-end cash forecast computed and displayed in Overview
- [ ] Goal completion forecast uses actual contribution trend
- [ ] Burn rate forecast triggers Today Mode alert when < 3 months runway
- [ ] Contribution gap forecast surfaced in goal detail and Monthly Review
- [ ] All forecasts include DerivedExplanation

-----

## F3.9 — Behavioral: Today Mode Integration

**Ref:** Section 5.5 + Obligations Addendum Section 5.3

Finance surfaces through existing Today Mode sections — no new sections or priority tiers:

|Existing Section      |Finance Integration                                                                  |
|----------------------|-------------------------------------------------------------------------------------|
|Due/overdue tasks (P1)|Tasks linked to accounts or financial goals; missed obligation alerts (high severity)|
|Goal nudges (P4)      |Financial goal progress, goal_off_track alerts, obligation impact on goals           |
|AI Briefing           |Financial anomalies as briefing bullets from Alerts Engine                           |

**Today Mode finance blocks** (from Alerts Engine high-severity routing):

|Block                  |Trigger                                |Primary Action                   |
|-----------------------|---------------------------------------|---------------------------------|
|Cash safety warning    |low_cash_runway alert                  |Review transactions or move funds|
|Goal contribution nudge|goal_off_track alert                   |Transfer now / adjust plan       |
|Anomaly alert          |large_transaction / spend_creep        |Inspect / categorize / dismiss   |
|Upcoming obligation    |upcoming_obligation (non-autopay, high)|Mark paid / fund account / snooze|
|Missed obligation      |missed_obligation                      |Investigate / mark paid / void   |

All subject to U-01 (max 2 unsolicited intelligence items) and U-02 (10-item Today Mode cap).

### Acceptance Criteria — F3.9

- [ ] High-severity finance alerts appear in Today Mode through P1/P4 channels
- [ ] Attention budget respected (U-01, U-02)
- [ ] No new Today Mode sections created
- [ ] Each finance item has one clear action + explanation

-----

## F3.10 — Behavioral: Financial Review Integration

**Ref:** Section 5.4

### F3.10.1 Weekly Financial Review (within Weekly Review)

- Net worth, liquid cash, and spending changes this week (from finance_weekly_rollups)
- Categories above/below normal weekly pattern (category_variance_flags)
- Uncategorized/unreconciled/suspicious transactions (from finance_alerts, status = active)
- Goal funding pace check (goal_allocations + balance_snapshots)
- Output feeds into weekly_snapshots.notes

### F3.10.2 Monthly Financial Review (within Monthly Review)

- Month-end net worth and liquid net worth change (from finance_monthly_rollups)
- Savings rate and top category variances vs prior month and 3-month baseline
- Goal progress delta and estimated completion date
- Investment performance: market movement vs deposits/withdrawals vs realized gains (from portfolio_rollups)
- Recommendations classified as Recommendations (D-04), dismissible

### Acceptance Criteria — F3.9

- [ ] Weekly Review shows financial section with variance flags
- [ ] Monthly Review shows investment performance attribution
- [ ] All recommendations dismissible and classified per D-04

-----

## F3.11 — Behavioral: AI Modes + Capture

### F3.11.1 AI Mode Financial Extensions

**Ref:** Section 5.8

|Mode   |Finance Extension                                      |Example                               |
|-------|-------------------------------------------------------|--------------------------------------|
|Ask    |Queries financial_transactions with filters            |“What did I spend on dining in March?”|
|Plan   |Creates financial goals, suggests contributions        |“Help me plan saving for a house”     |
|Reflect|Pulls Derived cashflow into narrative                  |“How was my spending this month?”     |
|Improve|Surfaces category trends, anomalies, leakage candidates|“Where can I cut spending?”           |

New retrieval mode: `financial_qa` — account: 1.0, goal(financial): 0.8, memory: 0.4, recency: 90 days, filter: active accounts.

### F3.11.2 Cmd+K Financial Quick-Capture

**Ref:** Section 5.7

- Typing `$` or a number triggers financial quick-capture
- Parsed as transaction with amount pre-filled
- Creates inbox_item if ambiguous, or directly creates financial_transaction if parseable
- **Source connections** (design doc Section 5.7): source items (investment articles, financial advice) link to accounts or financial goals via `captured_for` edges. Memory nodes (financial decisions) link via `semantic_reference`. These connections should work via the existing edge creation UI.

### F3.11.3 Financial Cleanup Queues

**Ref:** Section 5.6

Populated from finance_alerts with medium severity:

|Queue                     |Alert Type                     |Actions                             |
|--------------------------|-------------------------------|------------------------------------|
|Uncategorized transactions|uncategorized_aging            |Categorize, bulk categorize, dismiss|
|Stale accounts            |(is_active but no activity 90d)|Deactivate, update balance, snooze  |
|Unreconciled balances     |unreconciled_divergence        |Reconcile, add adjustment, snooze   |
|Broken transfers          |broken_transfer                |Fix pairing, void orphan, dismiss   |
|Pending transactions      |stale_pending                  |Post, void, snooze                  |
|Duplicate imports         |duplicate_import               |Merge, keep both, void duplicate    |

### F3.11.4 Obligation Context Layer

**Ref:** Obligations Addendum Section 5.4

When viewing an obligation in the detail pane, the context layer shows (following v6 Section 9.2 priority order):

1. **Backlinks**: goals, memories, sources referencing this obligation
1. **Outgoing**: account it charges (obligation_charges_account), related obligations (bundles via semantic_reference)
1. **Provenance**: if promoted from detected pattern, link to originating recurring_pattern
1. **Activity**: recent matched transactions (last 3), next expected date, rate change history from breakdown versioning
1. **AI suggestions**: related obligations to bundle or compare

All within 8-item context layer cap (U-03).

### Acceptance Criteria — F3.11

- [ ] AI Ask mode answers financial queries with transaction data
- [ ] AI Improve mode surfaces leakage candidates and spending trends
- [ ] Cmd+K $ trigger creates transactions or inbox items
- [ ] Source → account/goal connections work via captured_for edges
- [ ] Memory → account connections work via semantic_reference
- [ ] Cleanup queues populated from medium-severity alerts
- [ ] Obligation detail pane shows context layer with backlinks, outgoing, provenance, activity
- [ ] Context layer respects U-03 (8-item cap)

-----

-----

# Phase F4: Advanced (Post-MVP)

**Design Doc Reference:** Section 8.4
**Duration:** Ongoing
**Prerequisite:** F3 complete

-----

## F4.1 — API Sync

- Plaid/SnapTrade integration as Behavioral service
- Runs on schedule or user trigger
- Produces transactions with source = api_sync, status = pending
- Append-only, consistent with T-02
- External_id for dedup

## F4.2 — Computed Balance Snapshots

- Nightly background job
- For accounts with transaction history but no snapshot for today: compute from last reconciled snapshot + SUM(signed_amount) since then
- Source = computed. Never overwrites reconciled snapshots (F-09).

## F4.3 — Cross-Domain Intelligence

**Ref:** Section 4.9

|Insight                   |Sources                                         |Classification|
|--------------------------|------------------------------------------------|--------------|
|Spending vs mood          |financial_transactions + journal_nodes.mood     |Correlational |
|Income vs productivity    |financial_transactions + task_execution_events  |Correlational |
|Financial stress indicator|High expense anomalies + low mood + missed tasks|Recommendation|
|Goal alignment            |Financial goal progress + general goal progress |Descriptive   |

## F4.4 — Forecasting Engine Enhancements

**Note:** Core forecasting engine is delivered in F3.8. This phase covers advanced extensions:

- Retirement planning projections (multi-decade horizons)
- Scenario modeling (“what if I increase contributions by $200/mo”)
- Monte Carlo simulation for goal probability
- Integration with recurring_patterns for improved obligation forecasting accuracy

## F4.5 — Lot-Level Cost Basis

- Activate `investment_transactions.lot_id`
- FIFO/LIFO/specific-lot cost basis calculations
- Realized gain computation from sell transactions vs cost basis

## F4.6 — Alert Personalization

- Track dismiss patterns per alert_type per user
- If user consistently dismisses a specific type, lower its default severity
- Configurable thresholds per alert type

## F4.7 — Budget / Spending Plan Configuration

- Category-level monthly budgets
- Variance tracking: actual vs budget
- Alerts when approaching or exceeding budget

## F4.8 — Behavioral Finance Intelligence

- Impulse detection (cluster of unplanned discretionary spend)
- Regret tagging (user marks transactions as regretted)
- Waste scoring (low-satisfaction repeated spend)
- Spending vs mood correlation surfaced in Reflect mode

-----

-----

# Dependency Graph

```
F1 (Foundation + Capture)
├── F2 (Intelligence + Decision Surfaces)
│   ├── F3 (Behavioral Integration + Patterns)
│   │   └── F4 (Advanced — post-MVP)
│   └── F4 (Advanced — post-MVP)
└── F4.1 (API Sync — can start after F1 + F1.3 audit trail)
```

Phase F1 is the critical path. F2 and F3 are sequential (each builds on the prior). F4 items can be cherry-picked independently once F3 is complete.

-----

# Invariant Enforcement Schedule

|Invariant|Introduced|Description                                        |
|---------|----------|---------------------------------------------------|
|F-01     |F1        |Transactions never become nodes                    |
|F-02     |F1        |Amount always positive, direction in type          |
|F-03     |F1        |Financial goal field consistency                   |
|F-04     |F1        |Balance snapshot uniqueness                        |
|F-05     |F1        |Transfer pairing (exactly 2 per group)             |
|F-06     |F1        |No shadow graph (edges only, no ID arrays)         |
|F-07     |F2        |Cashflow excludes transfers and investments        |
|F-08     |F1        |Balance computations use posted/settled only       |
|F-09     |F1        |Reconciled snapshots are authoritative             |
|F-10     |F2        |Historical FX uses snapshot-date rates             |
|F-11     |F1        |Audit trail on every transaction mutation          |
|F-12     |F1        |Category deletion blocked by referential integrity |
|F-13     |F1        |Goal allocation percentage bounds ≤ 1.0 per account|
|F-14     |F2        |Alert deduplication via dedup_key                  |
|F-15     |F2        |Alerts are projection, not source of truth         |
|F-16     |F3        |Recurring pattern confidence thresholds            |
|F-17     |F2        |Obligation amount model consistency                |
|F-18     |F2        |Obligation status lifecycle                        |
|F-19     |F2        |next_expected_date is Derived                      |
|F-20     |F2        |Breakdown amount model consistency                 |
|F-21     |F2        |One active breakdown version per normalized_name   |
|F-22     |F2        |Deprecated breakdown has end date                  |
|F-23     |F3        |Seasonal confidence threshold                      |
|F-24     |F3        |Seasonality requires consecutive deviation         |
|F-25     |F3        |Obligation event uniqueness per date               |
|F-26     |F3        |Obligation event ownership alignment               |

-----

# Session Map

Each phase is broken into implementation sessions scoped for one Claude Code context window. Each session references the plan sections it covers, lists the invariants enforced, and specifies the reference documents needed.

## Phase F1: Foundation + Capture — 4 Sessions

### Session F1-A: Database Schema

**Plan sections:** F1.1, F1.2, F1.3
**Delivers:** All database migrations for Phase F1.

- F1.1: account_nodes table, goal_nodes extension (goal_type, target_amount, current_amount, currency), goal_allocations table, financial_categories table (with system seed data), account_funds_goal edge type-pair constraint, `account` added to nodes.type ENUM
- F1.2: financial_transactions table (with signed_amount generated column, all 11 transaction_type values, status lifecycle, transfer_group_id), balance_snapshots table (with reconciliation fields). All indexes: (account_id, occurred_at), (user_id, occurred_at), (account_id, external_id) partial, (transfer_group_id) partial, (category_id), (status), (account_id, snapshot_date) unique.
- F1.3: financial_transaction_history table (append-only audit log)
- Schema comments tagging CACHED DERIVED and BEHAVIORAL TRACKING fields per S-01

**Invariants enforced at DB level:** F-02 (signed_amount generation with pending → 0), F-04 (balance snapshot uniqueness), F-08 (signed_amount pending behavior), F-12 (category FK prevents deletion)
**Reference docs:** v6 architecture, finance design Rev 3

-----

### Session F1-B: Backend Core Services

**Plan sections:** F1.1 (services), F1.2 (services, partial), F1.3 (trigger)
**Delivers:** Backend services and API routes for Core financial entities.

- Account domain: CRUD (create node + companion in transaction), list (active/inactive filter), detail, update, soft deactivate
- Goal financial extension: validation for F-03 (financial goals require target_amount + currency; general goals require all financial fields null)
- Category CRUD: hierarchy support, system vs user-created, F-12 deletion blocking
- Allocation CRUD: F-13 bounds validation (percentage sum ≤ 1.0 per account across all goals), F-06 enforcement (no shadow graph)
- Edge creation: account_funds_goal with type-pair validation (G-01)
- Audit trail: database trigger or application middleware ensuring F-11 (every financial_transaction mutation → history row)

**Invariants enforced at app level:** F-01 (transactions never nodes), F-03 (goal field consistency), F-06 (no shadow graph), F-09 (reconciled snapshots authoritative), F-13 (allocation bounds)
**Reference docs:** v6 architecture, finance design Rev 3

-----

### Session F1-C: Backend Temporal Services

**Plan sections:** F1.2 (services), F1.4
**Delivers:** Transaction services, balance services, and capture workflows.

- Transaction CRUD: create (with audit history), update (with audit history), void (with audit history). Status lifecycle: pending → posted → settled. Transfer pairing: exactly 2 records per transfer_group_id (F-05), 1 transfer_out + 1 transfer_in, orphan detection.
- Balance snapshot CRUD: manual entry, reconciliation marking. Balance authority rule: reconciled snapshot = source of truth, computed balance never overrides (F-09).
- CSV import service: upload → column mapping → saved mappings per account → dedup via UNIQUE(account_id, external_id) → preview with error/duplicate highlighting → bulk insert on confirm. Auto-generate balance_snapshots if balance column present.
- Manual entry defaults: most recently used account, date = today, status = posted.

**Invariants enforced at app level:** F-02 (positive amounts only), F-05 (transfer pairing), F-08 (balance queries use posted/settled only), F-09 (reconciliation authority), F-11 (audit on every mutation)
**Reference docs:** v6 architecture, finance design Rev 3

-----

### Session F1-D: Frontend

**Plan sections:** F1.5
**Delivers:** All Phase F1 frontend work.

- Finance rail entry: `$` icon in nav rail with cyan active accent
- Account list view: name, type, institution, current balance, active/inactive badge
- Account detail panel: metadata + transaction list filtered to account + balance history
- Transaction list: filterable by account, date range, type, category, status, amount range. State chips for pending/posted/settled/uncategorized.
- Transaction detail sheet: all fields, edit capability, audit history link
- Category management: CRUD with hierarchy display
- Manual transaction entry form: account, amount, type, category (hierarchical dropdown), date. Smart defaults (last account, today).
- CSV import UI: file upload → column mapping → preview → confirm
- Balance snapshot form: account, balance, date, reconciliation checkbox

**Design tokens:** v6 Section 9.4. **Typography:** v6 Section 9.3. **Layout:** v6 Section 9.1.
**Reference docs:** v6 architecture, finance design Rev 3

-----

## Phase F2: Intelligence + Decision Surfaces — 5 Sessions

### Session F2-A: Database Schema

**Plan sections:** F2.1, F2.3 (tables only), F2.4 (table only), F2.6 (tables only)
**Delivers:** All database migrations for Phase F2.

- F2.1: investment_holdings, investment_transactions (with UNIQUE partial on external_id), exchange_rates (with UNIQUE on currency pair + date), market_prices cache (with UNIQUE on symbol + date + source)
- F2.3: finance_daily_rollups, finance_weekly_rollups, finance_monthly_rollups, portfolio_rollups
- F2.4: finance_alerts table (with dedup_key, entity_refs JSONB, explanation JSONB, lifecycle status ENUM)
- F2.6: obligation_nodes (all fields from addendum), obligation_breakdowns (with effective_from/effective_to versioning), obligation_charges_account and obligation_impacts_goal edge type-pair constraints, semantic_reference updates for obligation pairs, `obligation` added to nodes.type ENUM
- All indexes including obligation partial unique indexes (F-21)

**Invariants enforced at DB level:** F-10 (exchange_rates uniqueness), F-21 (partial unique on obligation_id + normalized_name WHERE effective_to IS NULL)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F2-B: Backend Investment + Obligation Services

**Plan sections:** F2.1 (services), F2.6 (services)
**Delivers:** Backend services and API routes for investment and obligation entities.

- Investment holdings CRUD: snapshot-based, per account per date
- Investment transactions CRUD: buy, sell, dividend_reinvest, split, merger, spinoff. Corporate action handling (split adjusts quantity + price_per_unit).
- Exchange rate service: store historical rates, lookup by currency pair + date
- Market price cache: manual entry for MVP, CRUD
- Obligation CRUD: create (node + companion in transaction), update, cancel, pause/resume. F-17 (amount model consistency), F-18 (status lifecycle: cancelled requires ended_at), F-19 (next_expected_date is CACHED DERIVED), F-20 (breakdown amount model), F-22 (deprecated breakdown has end date)
- Obligation breakdown management: add component, version on rate change (set effective_to on old, create new with effective_from), F-21 enforcement

**Invariants enforced at app level:** F-17, F-18, F-19, F-20, F-21, F-22
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F2-C: Backend Derived Intelligence

**Plan sections:** F2.2, F2.3 (refresh logic)
**Delivers:** All Derived computation services for Phase F2.

- Net worth engine: sum account balances (most recent snapshot ≤ target date), liabilities subtracted (loan, mortgage, credit_card), multi-currency via exchange_rates at snapshot date (F-10). Liquid net worth excludes illiquid assets.
- Cashflow analytics: monthly_income, monthly_expenses, net_cashflow, savings_rate, burn_rate. F-07: transfers and investment types excluded.
- Spending intelligence: category breakdown with hierarchy rollup per period. Trend detection (1.5× rolling 3-month average). Anomaly detection (3× category median with DerivedExplanation). Merchant concentration (30% threshold, fuzzy matching pre-F3). Spend creep (rolling 3-month average comparison across consecutive windows). Leakage candidates (frequency-based heuristics pre-F3).
- Financial goal progress: current_amount from allocations, progress_pct, projected_completion (linear 90-day), monthly_contribution_needed. Background job updates goal_nodes.current_amount.
- Investment performance: total_value, total_cost_basis, unrealized_gain, simple_return, dividend_income. Realized gain uses average cost basis (lot tracking in F4).
- Rollup refresh: daily rollups event-driven on transaction insert/update. Weekly, monthly, portfolio rollups via nightly job.

**Invariants enforced:** F-07 (cashflow exclusion), F-10 (historical FX), D-01 (DerivedExplanation on user-facing outputs), D-02 (all outputs recomputable)
**Reference docs:** v6 architecture, finance design Rev 3

-----

### Session F2-D: Backend Alerts Engine

**Plan sections:** F2.4, F2.6.6
**Delivers:** Complete Alerts Engine with rule-based detection.

- finance_alerts service: CRUD, dedup via dedup_key (F-14), lifecycle management (active → dismissed/snoozed/resolved)
- DerivedAlertCandidate pipeline: each detection function produces { type, severity, entity_refs, explanation (DerivedExplanation), score, dedup_key }
- Detection loop: configurable schedule (default 6 hours). Deduplicate → upsert. Auto-resolution: if candidate no longer produced on subsequent loop, status → resolved.
- 8 rule-based alert types: low_cash_runway, large_transaction, uncategorized_aging, duplicate_import, stale_pending, goal_off_track, unreconciled_divergence, broken_transfer
- 5 rule-based obligation alert types: upcoming_obligation (dynamic lead time: base 3 days, autopay → 1 day, variance → extend, clamped [1,7]), missed_obligation (deferred 5 days if autopay=true), obligation_amount_spike (>20% of expected/seasonal), obligation_rate_change (2 consecutive months ±5%), obligation_expiring (end date within 14 days)
- Three-tier routing: high → Today Mode (P1/P4), medium → Finance Review Queue, low → finance module only
- F-15: table is stateful projection, not source of truth

**Invariants enforced:** F-14 (alert dedup), F-15 (projection not truth), D-01 (DerivedExplanation on every alert)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F2-E: Frontend

**Plan sections:** F2.5, F2.6.7
**Delivers:** All Phase F2 frontend work.

- Overview screen: net worth hero with period switcher (chart + narrative update together), liquid net worth toggle. Cashflow cards (income, expenses, net cashflow, savings rate) with pending/posted distinction. Insights panel: active alerts with primary action + explanation, split descriptive from action metrics. Reference UX-to-system mapping (finance doc Section 6).
- Account list enhancements: reconciliation state badges (current, stale, needs review)
- Account detail enhancements: balance history, pending transaction total, upcoming obligations placeholder
- Credit accounts: utilization and statement due context
- Holdings view: portfolio composition per brokerage, market movement vs contributions (from portfolio_rollups), concentration/diversification warnings
- Brokerage accounts: liquid vs illiquid treatment
- Financial goal progress cards: current_amount, target_amount, progress_pct, projected completion. Actionable: transfer, adjust target, revise deadline.
- Obligation management UI: create/edit form (type, recurrence, amount model, expected amount/range, account, category, autopay, cancellation URL), breakdown editor (add/edit/version components), link to account and goal via edge UI
- Graph connection verification: all connections from finance doc Section 2.4 and obligations addendum Section 2.4 visible in context layer

**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

## Phase F3: Behavioral Integration + Patterns — 5 Sessions

### Session F3-A: Database Schema

**Plan sections:** F3.1 (table), F3.2 (table — now renumbered as counterparty), F3.3 (table — now renumbered as counterparty), F3.4 (table), F3.5 (table)
**Delivers:** All database migrations for Phase F3.

- obligation_events table with indexes: (obligation_id, expected_for_date), (user_id, expected_for_date), (transaction_id) partial WHERE NOT NULL
- counterparty_entities table with UNIQUE(user_id, canonical_name). Enable counterparty_entity_id FK on financial_transactions (was nullable/deferred). Add index (counterparty_entity_id) partial WHERE NOT NULL on financial_transactions.
- recurring_patterns table
- obligation_seasonal_profiles table with indexes: (obligation_id, period_type, period_value), (obligation_id, breakdown_id)

**Invariants enforced at DB level:** F-25 (obligation event uniqueness — partial unique index)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F3-B: Backend Matching + Patterns

**Plan sections:** F3.1 (services), F3.3 (services), F3.4 (services), F3.6
**Delivers:** Obligation events, transaction matching, counterparty resolution, and recurring pattern detection.

- Obligation events service: CRUD with F-25 uniqueness (one terminal event per obligation per expected_for_date), F-26 ownership alignment. Correct data flow: transaction posts → Derived matching → obligation_event created (Temporal) → Derived recomputes next_expected_date. Derived never mutates Derived directly.
- Transaction-to-obligation matching: weighted confidence (counterparty_entity 0.45, amount within range 0.20, timing ±5 days 0.20, category 0.10, account 0.05). Auto-link ≥ 0.7, suggestion 0.4–0.7, below 0.4 no match. Match accepted → obligation_event(paid). No match by expected + lead_time → obligation_event(missed) → Alerts Engine fires.
- Counterparty entity resolution: on transaction import/create, match raw counterparty against aliases. Match found → set counterparty_entity_id, auto-populate category if transaction has none. No match → store raw string. Background job clusters similar raw strings and suggests new entities. Merge/rename updates all referenced transactions.
- Recurring pattern detection: group transactions by (account_id, counterparty/entity, approximate amount). 3+ occurrences → classify frequency from median interval (~7d weekly, ~14d biweekly, ~30d monthly, ~90d quarterly, ~365d annual). Confidence from interval regularity + amount consistency. F-16: < 0.5 not surfaced, 0.5–0.7 suggestions, > 0.7 auto-classified. Two-stage lifecycle: high-confidence pattern → user confirms → promotes to obligation_node (Promotion Contract, v6 Section 5.8, provenance edge).

**Invariants enforced:** F-16 (confidence thresholds), F-25 (event uniqueness), F-26 (ownership alignment), B-01 (Promotion Contract)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F3-C: Backend Derived Intelligence

**Plan sections:** F3.5, F3.8
**Delivers:** Seasonal intelligence and forecasting engine.

- Seasonal intelligence: obligation_seasonal_profiles computation. Confidence calculation: `confidence = 0.4 × min(sample_count/6, 1.0) + 0.35 × variance_stability + 0.25 × recency_score`. Variance stability = 1 - CV, clamped [0,1]. Recency score exponential decay, half-life 12 months. Seasonality detection (6-step algorithm from addendum Section 4.3): collect 24 months weighted by recency → annual baseline (weighted median, p25, p75) → group by period → compute seasonality_strength per period → flag is_seasonal if 2+ consecutive periods |strength| > 0.5 → exclude confidence < 0.5 from alerting. F-23, F-24 enforcement. Rate change detection: 2 consecutive months at new amount ±5% → recommendation to update obligation.
- Downstream consumer integration: anomaly detection uses seasonal profiles (eliminates false positives), forecasting engine uses seasonal profiles for variable obligations, Alerts Engine uses seasonally-aware thresholds, Monthly Review references seasonal context.
- Forecasting engine (4 forecasts, all with DerivedExplanation): month-end cash forecast (transactions + recurring_patterns + balance_snapshots), goal completion forecast (actual contribution trend), burn rate forecast (liquid net worth / monthly_expenses, alert if < 3 months), contribution gap forecast (monthly amount to recover off-track goal).

**Invariants enforced:** F-23 (seasonal confidence threshold), F-24 (consecutive deviation), D-01 (DerivedExplanation on all forecasts)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F3-D: Backend Behavioral Workflows

**Plan sections:** F3.7, F3.9, F3.10, F3.11 (backend portions)
**Delivers:** Pattern-based alerts, Today Mode integration, review integration, AI modes, capture, cleanup.

- Pattern-based alerts (9 types added to Alerts Engine): subscription_detected, spend_creep, impulse_cluster, income_irregularity, missed_obligation, portfolio_drift, obligation_creep, obligation_concentration, obligation_optimization. All route through existing three-tier model.
- Today Mode integration: finance items sourced from Alerts Engine high-severity routing through existing P1 (due/overdue) and P4 (goal nudges) channels. Finance blocks: cash safety warning, goal contribution nudge, anomaly alert, upcoming obligation, missed obligation. Each with one clear action + explanation. U-01 (max 2 unsolicited) and U-02 (10-item cap) enforced.
- Weekly review financial section: net worth/liquid cash/spending changes (finance_weekly_rollups), category variance flags, uncategorized/unreconciled/suspicious transactions (finance_alerts active), goal funding pace. Output → weekly_snapshots.notes.
- Monthly review financial section: month-end net worth change (finance_monthly_rollups), savings rate + category variances vs prior month + 3-month baseline, goal progress delta + estimated completion, investment performance split (market movement vs deposits/withdrawals vs realized gains from portfolio_rollups). Recommendations classified per D-04, dismissible.
- AI mode financial extensions: Ask (transaction queries), Plan (financial goals + contributions), Reflect (cashflow narrative), Improve (trends, anomalies, leakage). New retrieval mode: financial_qa (account 1.0, goal(financial) 0.8, memory 0.4, 90 days, active accounts).
- Cmd+K financial capture: $ or number triggers financial quick-capture. Parseable → financial_transaction. Ambiguous → inbox_item. Source connections: source items → accounts/goals via captured_for, memory → accounts via semantic_reference.
- Financial cleanup queues (6, populated from medium-severity alerts): uncategorized transactions, stale accounts, unreconciled balances, broken transfers, pending transactions, duplicate imports.

**Invariants enforced:** U-01 (max 2 unsolicited), U-02 (10-item Today Mode cap), D-04 (analytics output classification), B-01 (Promotion Contract for source connections)
**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

### Session F3-E: Frontend

**Plan sections:** F3.9 (UI), F3.10 (UI), F3.11 (UI)
**Delivers:** All Phase F3 frontend work.

- Today Mode finance items: cash safety warning, goal contribution nudge, anomaly alert, upcoming/missed obligation. Each with one clear action + explanation. Respects attention budget.
- Weekly review: financial section with variance flags, alert summary, goal funding status
- Monthly review: financial section with investment performance attribution, recommendations (dismissible)
- Obligation detail pane: context layer following v6 Section 9.2 priority order — (1) backlinks: goals, memories, sources, (2) outgoing: account it charges, related obligations/bundles, (3) provenance: link to originating recurring_pattern if promoted, (4) activity: last 3 matched transactions, next expected date, rate change history, (5) AI suggestions: related obligations to bundle/compare. All within U-03 (8-item cap).
- Cleanup queue UI: 6 queues with batch actions per queue definition
- Cmd+K: $ trigger in command palette, financial quick-capture flow
- Source → account/goal edge creation via captured_for in edge UI

**Reference docs:** v6 architecture, finance design Rev 3, obligations addendum

-----

# Implementation Notes

## Session Strategy

Each session should be executed in a fresh Claude Code context window. Pass the following as context:

1. `personal-os-architecture-v6.docx` — the constitutional reference
1. `finance-module-design-rev3.docx` — the canonical finance spec
1. `obligations-addendum.docx` — the obligations spec (needed from F2-A onward)
1. `finance-implementation-plan.md` — this plan, scoped to the current session

## Testing Strategy

- **Schema invariants**: write database-level constraints and triggers for hard invariants (F-02 signed_amount generation, F-04 uniqueness, F-05 transfer pairing count, F-11 audit trigger, F-21 partial unique, F-25 event uniqueness)
- **Application invariants**: write validation middleware for soft invariants (F-03 goal field consistency, F-13 allocation bounds, F-17/F-20 amount model consistency, F-16 confidence thresholds)
- **Integration tests**: per-session acceptance criteria from the plan sections map directly to test cases

## Migration Strategy

- Each session that includes schema work produces its own Alembic migration file(s)
- Migrations are additive — no destructive changes to existing tables
- System-seeded categories created via data migration, not application code

-----

*— End of Plan —*