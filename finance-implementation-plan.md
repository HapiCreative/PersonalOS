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

**Ref:** Obligations Addendum Section 8.1 — “Finance Phase 2 Additions”

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

### Acceptance Criteria — F3.5

- [ ] Seasonal profiles computed for variable/seasonal obligations
- [ ] Confidence thresholds enforced (F-23)
- [ ] Seasonality correctly requires consecutive deviation (F-24)
- [ ] Rate changes detected after 2 consecutive months

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

# Implementation Notes

## Session Strategy

Each phase should be executed in a fresh Claude Code context window. Pass the following as context:

1. `personal-os-architecture-v6.docx` — the constitutional reference
1. `finance-module-design-rev3.docx` — the canonical finance spec
1. `obligations-addendum.docx` — the obligations spec (for F3)
1. This implementation plan — scoped to the current phase

## Testing Strategy

- **Schema invariants**: write database-level constraints and triggers for hard invariants (F-02 signed_amount generation, F-04 uniqueness, F-05 transfer pairing count, F-11 audit trigger)
- **Application invariants**: write validation middleware for soft invariants (F-03 goal field consistency, F-13 allocation bounds, F-17/F-20 amount model consistency)
- **Integration tests**: per-phase acceptance criteria map directly to test cases

## Migration Strategy

- Each phase produces its own Alembic migration file(s)
- Migrations are additive — no destructive changes to existing tables
- System-seeded categories created via data migration, not application code

-----

*— End of Plan —*