# PERSONAL OS

## Finance Module Design Document

Architecture v6 Addendum | April 2026 | Revision 3

*Full Financial OS: Budget Tracking + Investments + Goals + Projections + Alerts*

> **Core:** Accounts, Financial Goals (extended goal_nodes), Categories, Counterparty Entities
> 
> **Temporal:** Transactions, Balance Snapshots, Investment Holdings, Investment Transactions, Audit Trail
> 
> **Derived:** Net Worth, Cashflow, Spending Intelligence, Performance, Recurring Patterns, Alert Candidates
> 
> **Behavioral:** Alerts Engine, Capture, Reviews, Today Mode Integration, AI Extensions

# 1. Architecture Overview

The finance module follows the Personal OS four-layer architecture. Financial entities are distributed across layers based on the governing principle:

*“The graph is for meaning. Tables are for behavior and time.”*

## 1.1 Layer Distribution

|**Layer** |**Finance Representation**                                          |**Examples**                                                                                                             |
|----------|--------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
|Core      |Durable, user-owned financial entities that participate in the graph|Accounts, Financial Goals (extended goal_nodes), Categories, Counterparty Entities (deferred)                            |
|Temporal  |Append-only financial behavior records indexed by time              |Transactions, Balance Snapshots, Investment Holdings, Investment Transactions, Audit Trail                               |
|Derived   |Recomputable intelligence from Core + Temporal                      |Net Worth, Cashflow Analytics, Spending Patterns, Investment Performance, Recurring Patterns (deferred), Alert Candidates|
|Behavioral|Workflows that orchestrate financial actions                        |Alerts Engine, Transaction Capture, CSV Import, Financial Reviews, AI Mode Extensions                                    |

## 1.2 Governing Constraints

**Constraint 1:** Transactions NEVER become nodes. No transaction-level graph edges. They are behavioral records, not semantic entities.

**Constraint 2:** Accounts are the bridge between financial behavior and the graph. All cross-domain intelligence flows through account and goal nodes.

**Constraint 3:** Budget categories are Core configuration entities with hierarchical support, not free-text fields.

**Constraint 4:** All financial Derived outputs use the DerivedExplanation schema (Invariant D-01).

**Constraint 5:** Finance extends existing workflows (Today Mode, Weekly Review, AI Modes) rather than creating parallel ones.

**Constraint 6:** All financial amounts use TIMESTAMPTZ for temporal precision and NUMERIC(15,2) for monetary values. No DATE-only fields for transaction timing.

**Constraint 7:** Alerts are a Behavioral materialization of Derived signals. The finance_alerts table is a stateful projection, not a source of truth.

*▶ [Rev3 CHANGE] Constraint 7 is new. Defines Alerts Engine architectural position.*

## 1.3 Data Ingestion Strategy

MVP: Manual entry + CSV import. Post-MVP: Optional bank/broker sync via open APIs (Plaid, SnapTrade). The system is fully functional without external dependencies. Sync is additive, never required.

# 2. Core Layer: Financial Entities

Four entity types participate in the Core layer. Financial goals are modeled as an extension of the existing goal_nodes table. Categories and Counterparty Entities are configuration tables.

*▶ [Rev3 CHANGE] Counterparty Entities added as specified-but-deferred Core configuration table.*

## 2.1 account_nodes

Accounts are durable, user-owned entities representing bank accounts, credit cards, brokerages, wallets, and loans. They are the primary bridge between financial behavior (Temporal) and the semantic graph (Core).

|**Column**           |**Type**             |**Description**                                                                      |
|---------------------|---------------------|-------------------------------------------------------------------------------------|
|node_id              |UUID (PK, FK → nodes)|1:1 with nodes. node type = account                                                  |
|account_type         |ENUM                 |checking, savings, credit_card, brokerage, crypto_wallet, cash, loan, mortgage, other|
|institution          |TEXT NULL            |Bank/broker name (e.g. Chase, Fidelity, Coinbase)                                    |
|currency             |TEXT                 |Primary currency (ISO 4217: USD, EUR, GBP, etc.)                                     |
|account_number_masked|TEXT NULL            |Last 4 digits only, for identification                                               |
|is_active            |BOOLEAN DEFAULT true |Whether account is currently in use                                                  |
|notes                |TEXT NULL            |Additional context                                                                   |

## 2.2 goal_nodes Extension (Financial Goals)

Financial goals are modeled by extending the existing goal_nodes table with three nullable financial fields and a goal_type discriminator. This avoids duplicating status, lifecycle, and edge logic.

**New fields added to goal_nodes:**

|**Column**    |**Type**            |**Layer**     |**Description**                                                                            |
|--------------|--------------------|--------------|-------------------------------------------------------------------------------------------|
|goal_type     |ENUM DEFAULT general|Core          |general or financial. Discriminator for financial goal behavior.                           |
|target_amount |NUMERIC(15,2) NULL  |Core          |Financial target amount. NULL for general goals.                                           |
|current_amount|NUMERIC(15,2) NULL  |CACHED DERIVED|Computed from account allocations (see goal_allocations). NULL for general goals. See S-01.|
|currency      |TEXT NULL           |Core          |Currency of target_amount (ISO 4217). NULL for general goals.                              |

*Invariant F-03: For goals with goal_type = financial, target_amount and currency must be non-null. For goals with goal_type = general, all three financial fields must be null.*

## 2.3 New Edge Relation: account_funds_goal

|**Relation**      |**Category**        |**Allowed Source → Target**|**Semantics**                                    |
|------------------|--------------------|---------------------------|-------------------------------------------------|
|account_funds_goal|Financial / Workflow|account → goal             |Account contributes funds toward a financial goal|

This relation is added to the Edge Type-Pair Constraints table in the v6 architecture. No other new edge types are needed; existing relations (semantic_reference, captured_for, goal_tracks_task) handle all other cross-domain financial connections.

## 2.4 Graph Connections

|**Connection**          |**Edge Relation**   |**Example**                                    |
|------------------------|--------------------|-----------------------------------------------|
|Account → Financial Goal|account_funds_goal  |Savings account funds house down payment goal  |
|Goal → Task             |goal_tracks_task    |Financial goal tracked by monthly transfer task|
|Memory → Account        |semantic_reference  |Decision to switch banks linked to new account |
|Source → Goal           |source_supports_goal|Investment article linked to retirement goal   |
|Source → Account        |captured_for        |Broker review captured for brokerage account   |
|Journal → Account       |journal_reflects_on |Journal entry reflecting on spending habits    |

## 2.5 financial_categories (Core Configuration)

Categories are structured configuration entities with optional hierarchy. They ensure consistent aggregation across transactions and enable meaningful spending intelligence.

|**Column**|**Type**                             |**Description**                                   |
|----------|-------------------------------------|--------------------------------------------------|
|id        |UUID (PK)                            |Primary key                                       |
|user_id   |UUID (FK → users)                    |Owner                                             |
|name      |TEXT                                 |Category name (e.g. Groceries, Rent, Dining)      |
|parent_id |UUID NULL (FK → financial_categories)|Parent category for hierarchy (e.g. Dining → Food)|
|icon      |TEXT NULL                            |Optional icon identifier                          |
|is_system |BOOLEAN DEFAULT false                |System-provided default vs user-created           |
|sort_order|INTEGER DEFAULT 0                    |Display ordering                                  |
|created_at|TIMESTAMPTZ                          |Creation timestamp                                |

*Constraint: UNIQUE(user_id, name, parent_id). No duplicate category names within the same parent.*

System-seeded defaults (Groceries, Rent, Utilities, Dining, Transportation, Entertainment, Healthcare, etc.) are created for new users. Users can rename, reorganize, or add custom categories.

## 2.6 goal_allocations

Defines what portion of each account’s balance contributes toward a financial goal. Solves the double-counting problem where multiple goals share the same account.

|**Column**     |**Type**         |**Description**                     |
|---------------|-----------------|------------------------------------|
|id             |UUID (PK)        |Primary key                         |
|goal_id        |UUID (FK → nodes)|Financial goal node                 |
|account_id     |UUID (FK → nodes)|Contributing account                |
|allocation_type|ENUM             |percentage or fixed                 |
|value          |NUMERIC(15,4)    |Percentage (0.0–1.0) or fixed amount|
|created_at     |TIMESTAMPTZ      |Creation timestamp                  |
|updated_at     |TIMESTAMPTZ      |Last modification                   |

*Constraint: UNIQUE(goal_id, account_id). One allocation per goal-account pair.*

**Financial Goal Progress Calculation:**

current_amount = SUM(account_balance * allocation_percentage) or SUM(MIN(account_balance, fixed_amount)) across all allocations for the goal. This prevents the same dollar from being counted toward multiple goals.

## 2.7 counterparty_entities (Core Configuration — Deferred)

*◆ [DEFERRED] Specified in Rev3. Implementation deferred to Phase 3+. Referenced by financial_transactions.counterparty_entity_id.*

Normalized merchant/counterparty records for consistent tracking across transactions. Enables merchant-level spending intelligence, recurring detection, and concentration analysis.

|**Column**     |**Type**                             |**Description**                                                              |
|---------------|-------------------------------------|-----------------------------------------------------------------------------|
|id             |UUID (PK)                            |Primary key                                                                  |
|user_id        |UUID (FK → users)                    |Owner                                                                        |
|canonical_name |TEXT                                 |Normalized display name (e.g. “Starbucks”, not “STARBUCKS #12345 NYC”)       |
|aliases        |TEXT[]                               |Raw counterparty strings that map to this entity                             |
|category_id    |UUID NULL (FK → financial_categories)|Default category for transactions from this counterparty                     |
|merchant_type  |ENUM NULL                            |retailer, employer, utility, subscription, government, transfer_target, other|
|is_subscription|BOOLEAN DEFAULT false                |Whether this counterparty represents a recurring subscription                |
|url            |TEXT NULL                            |Website for reference                                                        |
|notes          |TEXT NULL                            |User notes about this counterparty                                           |
|created_at     |TIMESTAMPTZ                          |Creation timestamp                                                           |
|updated_at     |TIMESTAMPTZ                          |Last modification                                                            |

*Constraint: UNIQUE(user_id, canonical_name). No duplicate canonical names per user.*

**Resolution flow:**

- On transaction import/create, the raw counterparty string is matched against aliases in counterparty_entities.
- If a match is found, counterparty_entity_id is set on the transaction. The entity’s default category_id can auto-populate if the transaction has no category.
- If no match is found, the raw counterparty string is stored as-is. A Behavioral job periodically clusters similar raw strings and suggests new counterparty entities for user review.
- Users can manually create, merge, or rename counterparty entities. Merging updates all referenced transactions.

## 2.8 Entities Explicitly NOT in Core

- Transactions: Temporal. Append-only behavior records. Never nodes, never edges.
- Holdings/Positions: Temporal. Snapshots of portfolio state at a point in time.
- Market Prices: Derived cache. Fetched externally, purged freely.
- Alerts: Behavioral stateful projections. Not source of truth. See Section 5.1.

# 3. Temporal Layer: Financial Behavior Records

All financial activity lives here. These tables follow the same admission criteria as all Temporal tables: time-bound, append-heavy, no graph edges, reference Core by ID only.

## 3.1 financial_transactions

Canonical record of all cash flow events. Each row represents one financial event: a purchase, income receipt, transfer, investment trade, etc.

|**Column**            |**Type**                              |**Layer**     |**Description**                                                                                                         |
|----------------------|--------------------------------------|--------------|------------------------------------------------------------------------------------------------------------------------|
|id                    |UUID (PK)                             |Temporal      |Primary key                                                                                                             |
|user_id               |UUID (FK → users)                     |Temporal      |Owner                                                                                                                   |
|account_id            |UUID (FK → nodes)                     |Temporal      |Account this transaction belongs to                                                                                     |
|transaction_type      |ENUM                                  |Temporal      |income, expense, transfer_in, transfer_out, investment_buy, investment_sell, dividend, interest, fee, refund, adjustment|
|status                |ENUM DEFAULT posted                   |Temporal      |pending, posted, settled. See status rules below.                                                                       |
|amount                |NUMERIC(15,2)                         |Temporal      |Absolute amount (always positive)                                                                                       |
|signed_amount         |NUMERIC(15,2) GENERATED               |CACHED DERIVED|PostgreSQL generated column. Positive for inflows, negative for outflows. See S-01.                                     |
|currency              |TEXT                                  |Temporal      |Transaction currency (ISO 4217)                                                                                         |
|category_id           |UUID NULL (FK → financial_categories) |Temporal      |Structured category reference                                                                                           |
|subcategory_id        |UUID NULL (FK → financial_categories) |Temporal      |Optional refinement (child of category_id)                                                                              |
|category_source       |ENUM DEFAULT manual                   |Temporal      |manual, system_suggested, imported                                                                                      |
|counterparty          |TEXT NULL                             |Temporal      |Raw merchant, employer, or transfer target string                                                                       |
|counterparty_entity_id|UUID NULL (FK → counterparty_entities)|Temporal      |Normalized counterparty reference. See Section 2.7.                                                                     |
|description           |TEXT NULL                             |Temporal      |User notes or imported memo                                                                                             |
|occurred_at           |TIMESTAMPTZ                           |Temporal      |User-perceived transaction timestamp                                                                                    |
|posted_at             |TIMESTAMPTZ NULL                      |Temporal      |Settlement/posting timestamp (for bank reconciliation)                                                                  |
|source                |ENUM                                  |Temporal      |manual, csv_import, api_sync                                                                                            |
|external_id           |TEXT NULL                             |Temporal      |Dedup key from CSV or bank sync                                                                                         |
|transfer_group_id     |UUID NULL                             |Temporal      |Links paired transfer_in/transfer_out rows                                                                              |
|tags                  |TEXT[] NULL                           |Temporal      |Freeform tags                                                                                                           |
|is_voided             |BOOLEAN DEFAULT false                 |Temporal      |Voided transactions excluded from calculations                                                                          |
|created_at            |TIMESTAMPTZ                           |Temporal      |Record creation                                                                                                         |
|updated_at            |TIMESTAMPTZ                           |Temporal      |Last modification                                                                                                       |

**Transaction Status Rules**

- pending: Transaction recorded but not yet confirmed. Excluded from balance calculations by default. Included in cashflow projections.
- posted: Confirmed transaction. Affects all balance and analytics calculations. Default for manual entry.
- settled: Final state. Funds fully cleared. Equivalent to posted for calculation purposes but signals reconciliation completeness.

*Invariant F-08: Balance computations must only include transactions where status IN (posted, settled) unless explicitly computing projected/pending balances.*

**Transfer Integrity Rules**

- Exactly 2 records per transfer_group_id: 1 transfer_out and 1 transfer_in. Application layer validates on create.
- Orphan detection: Cleanup system flags transfer_group_ids with count != 2 as broken transfers.
- Paired transaction reference: Each transfer row stores paired_transaction_id (the ID of its counterpart) for fast lookup.

**signed_amount Generation Rule**

GENERATED ALWAYS AS (amount * CASE WHEN transaction_type IN (‘income’, ‘transfer_in’, ‘refund’, ‘investment_sell’, ‘dividend’, ‘interest’) THEN 1 ELSE -1 END) STORED

Only applied when status IN (posted, settled). Pending transactions generate signed_amount = 0.

**Key Design Decisions**

- Amount is always positive. Direction is encoded in transaction_type. This avoids sign-confusion bugs.
- external_id enables idempotent imports. UNIQUE(account_id, external_id) WHERE external_id IS NOT NULL.
- category_source future-proofs for ML classification without over-building now.
- counterparty_entity_id references counterparty_entities (deferred). Until activated, raw counterparty string is the only merchant identifier.

**Indexes:**

(account_id, occurred_at), (user_id, occurred_at), (account_id, external_id) WHERE external_id IS NOT NULL, (transfer_group_id) WHERE transfer_group_id IS NOT NULL, (category_id), (status), (counterparty_entity_id) WHERE counterparty_entity_id IS NOT NULL

## 3.2 balance_snapshots

Point-in-time account balance records. Foundation for net worth tracking.

|**Column**   |**Type**             |**Description**                                      |
|-------------|---------------------|-----------------------------------------------------|
|id           |UUID (PK)            |Primary key                                          |
|user_id      |UUID (FK → users)    |Owner                                                |
|account_id   |UUID (FK → nodes)    |Account                                              |
|balance      |NUMERIC(15,2)        |Balance at snapshot time                             |
|currency     |TEXT                 |Currency (ISO 4217)                                  |
|snapshot_date|DATE                 |Date of snapshot                                     |
|source       |ENUM                 |manual, csv_import, api_sync, computed               |
|is_reconciled|BOOLEAN DEFAULT false|Whether this snapshot has been reconciled by the user|
|reconciled_at|TIMESTAMPTZ NULL     |When reconciliation occurred                         |
|created_at   |TIMESTAMPTZ          |Record creation                                      |

*Constraint: UNIQUE(account_id, snapshot_date). One snapshot per account per date.*

**Balance Authority Rule**

- Reconciled snapshot = source of truth. If a balance_snapshot with is_reconciled = true exists, that value is authoritative. Computed balances must not override it.
- Otherwise → computed balance. Balance = last known snapshot + SUM(signed_amount) from transactions since that snapshot, filtered to status IN (posted, settled).

*Invariant F-09: Computed balances must never override reconciled snapshots. Reconciled snapshots are user-verified truth.*

## 3.3 investment_holdings

Snapshot-based portfolio composition records. Each row represents what was held in an account on a given date.

|**Column**      |**Type**          |**Description**                                          |
|----------------|------------------|---------------------------------------------------------|
|id              |UUID (PK)         |Primary key                                              |
|user_id         |UUID (FK → users) |Owner                                                    |
|account_id      |UUID (FK → nodes) |Brokerage account                                        |
|symbol          |TEXT              |Ticker or asset identifier                               |
|asset_name      |TEXT NULL         |Human-readable name                                      |
|asset_type      |ENUM              |stock, etf, mutual_fund, bond, crypto, option, other     |
|quantity        |NUMERIC(15,6)     |Number of shares/units (6 decimals for fractional/crypto)|
|cost_basis      |NUMERIC(15,2) NULL|Total cost basis                                         |
|currency        |TEXT              |Currency                                                 |
|as_of_date      |DATE              |Date this snapshot represents                            |
|source          |ENUM              |manual, csv_import, api_sync, computed                   |
|valuation_source|ENUM              |market_api, manual, computed                             |
|created_at      |TIMESTAMPTZ       |Record creation                                          |

## 3.4 investment_transactions

Records individual investment activities that affect holdings. Separate from financial_transactions which tracks cash flow. This table tracks asset-level events.

|**Column**      |**Type**         |**Description**                                     |
|----------------|-----------------|----------------------------------------------------|
|id              |UUID (PK)        |Primary key                                         |
|user_id         |UUID (FK → users)|Owner                                               |
|account_id      |UUID (FK → nodes)|Brokerage account                                   |
|symbol          |TEXT             |Ticker or asset identifier                          |
|transaction_type|ENUM             |buy, sell, dividend_reinvest, split, merger, spinoff|
|quantity        |NUMERIC(15,6)    |Number of shares/units                              |
|price_per_unit  |NUMERIC(15,6)    |Price per share/unit at time of transaction         |
|total_amount    |NUMERIC(15,2)    |Total transaction value                             |
|currency        |TEXT             |Transaction currency                                |
|occurred_at     |TIMESTAMPTZ      |When the transaction occurred                       |
|lot_id          |TEXT NULL        |Future: lot identifier for tax lot tracking         |
|source          |ENUM             |manual, csv_import, api_sync                        |
|external_id     |TEXT NULL        |Dedup key                                           |
|notes           |TEXT NULL        |Additional context                                  |
|created_at      |TIMESTAMPTZ      |Record creation                                     |

*Constraint: UNIQUE(account_id, external_id) WHERE external_id IS NOT NULL.*

Corporate actions (splits, mergers, spinoffs) are modeled as investment_transactions. A 2:1 stock split creates a split-type row that adjusts quantity and price_per_unit for the affected holding. Lot tracking (lot_id) is a post-MVP field that enables FIFO/LIFO/specific-lot cost basis calculations.

## 3.5 exchange_rates

Historical exchange rate records for multi-currency net worth computation and transaction conversion.

|**Column**    |**Type**     |**Description**                                    |
|--------------|-------------|---------------------------------------------------|
|id            |UUID (PK)    |Primary key                                        |
|base_currency |TEXT         |Base currency (ISO 4217, e.g. USD)                 |
|quote_currency|TEXT         |Quote currency (ISO 4217, e.g. EUR)                |
|rate          |NUMERIC(15,8)|Exchange rate (1 base = rate quote)                |
|rate_date     |DATE         |Date this rate applies to                          |
|source        |TEXT         |Rate provider (e.g. ecb, manual, openexchangerates)|
|created_at    |TIMESTAMPTZ  |Record creation                                    |

*Constraint: UNIQUE(base_currency, quote_currency, rate_date).*

*Invariant F-10: Historical net worth calculations always use the exchange rate from the snapshot date, not the current date.*

## 3.6 financial_transaction_history

Immutable audit log of all changes to financial transactions. Financial data requires auditability that other Temporal records do not.

|**Column**    |**Type**                          |**Description**                        |
|--------------|----------------------------------|---------------------------------------|
|id            |UUID (PK)                         |Primary key                            |
|transaction_id|UUID (FK → financial_transactions)|Transaction being audited              |
|version       |INTEGER                           |Monotonically increasing version number|
|snapshot      |JSONB                             |Full transaction state at this version |
|change_type   |ENUM                              |create, update, void                   |
|changed_by    |UUID (FK → users)                 |Who made the change                    |
|changed_at    |TIMESTAMPTZ                       |When the change occurred               |

*Invariant F-11: Every mutation to a financial_transaction row must produce a corresponding financial_transaction_history row. Append-only, never modified or deleted.*

# 4. Derived Layer: Finance Intelligence

Everything in this section is recomputable from Core + Temporal. Nothing is source of truth. All user-facing outputs use DerivedExplanation (Invariant D-01). Storage is for performance, not permanence.

## 4.1 Net Worth Engine

Net worth = total assets minus total liabilities at a given point in time.

**Computation:**

For each account, find the most recent balance_snapshot on or before the target date. Accounts typed as loan, mortgage, credit_card are liabilities (balance subtracted). All others are assets (balance added). Multi-currency values converted to users.base_currency using exchange rates at snapshot date (from exchange_rates table, Invariant F-10).

**Liquid Net Worth**

In addition to total net worth, the system computes liquid_net_worth which excludes illiquid assets (real estate equity, retirement accounts, long-term locked investments). Account-level liquidity is determined by account_type: checking, savings, credit_card, cash, and crypto_wallet are liquid. brokerage depends on asset_type within holdings. loan, mortgage are always liabilities.

## 4.2 Cashflow Analytics

|**Metric**      |**Calculation**                                                                                      |**Refresh**          |
|----------------|-----------------------------------------------------------------------------------------------------|---------------------|
|monthly_income  |SUM(signed_amount) WHERE type IN (income, dividend, interest, refund) AND status IN (posted, settled)|On transaction insert|
|monthly_expenses|SUM(ABS(signed_amount)) WHERE type IN (expense, fee) AND status IN (posted, settled)                 |On transaction insert|
|net_cashflow    |monthly_income - monthly_expenses                                                                    |Derived from above   |
|savings_rate    |net_cashflow / monthly_income                                                                        |Derived from above   |
|burn_rate       |monthly_expenses / 30 (daily average)                                                                |Derived from above   |

Transfers and investment transactions are excluded from cashflow calculations. They move money between accounts, not in/out of the system.

*Invariant F-07: Transfer and investment transaction types are excluded from cashflow calculations.*

## 4.3 Spending Intelligence

**Category breakdown:**

Group expenses by category_id (with hierarchy rollup to parent categories) per period (week, month, quarter). Ranked by total spend. Uses structured category hierarchy from financial_categories.

**Trend detection:**

Compare current month category spend vs rolling 3-month average. Flag categories exceeding 1.5x average.

**Anomaly detection:**

Individual transactions exceeding 3x the median for that category are flagged. Uses DerivedExplanation schema with summary and factors array.

**Merchant concentration:**

*▶ [Rev3 CHANGE] New metric. Requires counterparty_entities (deferred). Until activated, computed from raw counterparty strings with fuzzy matching.*

Share of spend concentrated in a single merchant or counterparty. Flags when a single merchant exceeds a configurable threshold (default: 30% of category spend).

**Spend creep:**

*▶ [Rev3 CHANGE] New metric.*

Slow sustained increase in a category over multiple periods. Detected by comparing rolling 3-month averages across consecutive windows. Surfaced in Monthly Review and Improve mode.

**Leakage candidates:**

*▶ [Rev3 CHANGE] New metric. Requires recurring_patterns (deferred). Until activated, uses simple frequency-based heuristics.*

Low-value recurring or repeated discretionary spend that the user may not be consciously choosing to continue. Surfaced in Improve mode and subscription queue.

## 4.4 Financial Goal Progress

|**Metric**                 |**Calculation**                                                                   |
|---------------------------|----------------------------------------------------------------------------------|
|current_amount             |SUM of (account_balance * allocation) for all accounts linked via goal_allocations|
|progress_pct               |(current_amount / target_amount) * 100                                            |
|projected_completion       |Linear projection from contribution rate over last 90 days                        |
|monthly_contribution_needed|(target_amount - current_amount) / months_until_deadline                          |

current_amount on goal_nodes is updated by a background job that runs this calculation. The field is CACHED DERIVED; this computation is the source of truth.

## 4.5 Investment Performance

|**Metric**      |**Calculation**                                              |**Notes**                                  |
|----------------|-------------------------------------------------------------|-------------------------------------------|
|total_value     |SUM(quantity * current_price) per account                    |Current price from market data cache       |
|total_cost_basis|SUM(cost_basis) across holdings                              |From holdings snapshots                    |
|unrealized_gain |total_value - total_cost_basis                               |Per holding and aggregate                  |
|realized_gain   |From sell investment_transactions vs cost basis              |Uses lot tracking when available (post-MVP)|
|simple_return   |(current_value - total_invested + dividends) / total_invested|Quick portfolio metric                     |
|dividend_income |SUM from dividend transactions per period                    |Monthly, quarterly, annual                 |

## 4.6 Market Prices Cache

|**Column**|**Type**     |**Description**    |
|----------|-------------|-------------------|
|symbol    |TEXT         |Ticker             |
|price     |NUMERIC(15,4)|Latest known price |
|currency  |TEXT         |Price currency     |
|price_date|DATE         |As-of date         |
|source    |TEXT         |yahoo, manual, etc.|
|fetched_at|TIMESTAMPTZ  |When fetched       |

*Constraint: UNIQUE(symbol, price_date, source).*

## 4.7 Recurring Patterns (Derived — Deferred)

*◆ [DEFERRED] Specified in Rev3. Implementation deferred to Phase 3+. Feeds Alerts Engine, subscription detection, and obligation forecasting.*

Detected recurring transaction patterns. Computed from transaction history using frequency analysis. Used for subscription detection, upcoming obligation forecasting, and cashflow projection.

|**Column**            |**Type**                              |**Description**                                        |
|----------------------|--------------------------------------|-------------------------------------------------------|
|id                    |UUID (PK)                             |Primary key                                            |
|user_id               |UUID (FK → users)                     |Owner                                                  |
|account_id            |UUID (FK → nodes)                     |Account where pattern detected                         |
|counterparty          |TEXT NULL                             |Raw counterparty string                                |
|counterparty_entity_id|UUID NULL (FK → counterparty_entities)|Normalized counterparty (when activated)               |
|pattern_type          |ENUM                                  |subscription, income, bill, transfer, other            |
|category_id           |UUID NULL (FK → financial_categories) |Typical category for this pattern                      |
|frequency             |ENUM                                  |weekly, biweekly, monthly, quarterly, annual, irregular|
|expected_amount       |NUMERIC(15,2)                         |Median or mean amount                                  |
|amount_variance       |NUMERIC(15,2) NULL                    |Standard deviation of amount                           |
|last_occurrence       |TIMESTAMPTZ                           |Most recent matching transaction                       |
|next_expected         |DATE NULL                             |Predicted next occurrence                              |
|confidence            |FLOAT                                 |Detection confidence (0.0–1.0)                         |
|status                |ENUM                                  |active, paused, ended, user_confirmed, user_dismissed  |
|transaction_ids       |UUID[]                                |Historical transaction IDs forming this pattern        |
|computed_at           |TIMESTAMPTZ                           |When this pattern was last computed                    |

**Detection algorithm:**

- Group transactions by (account_id, counterparty / counterparty_entity_id, approximate amount).
- For each group with 3+ occurrences, compute inter-transaction intervals.
- Classify frequency based on median interval: ~7d = weekly, ~14d = biweekly, ~30d = monthly, ~90d = quarterly, ~365d = annual.
- Compute confidence based on regularity of intervals and amount consistency.
- Patterns with confidence < 0.5 are not surfaced. Patterns with confidence 0.5–0.7 are surfaced as suggestions. Patterns with confidence > 0.7 are auto-classified.
- Users can confirm or dismiss detected patterns. Confirmed patterns boost confidence to 1.0 and are used for cashflow projection.

**Downstream consumers:**

- Alerts Engine: missed expected payment, unexpected subscription charge, income irregularity.
- Cashflow forecasting: known obligations and expected income for month-end projection.
- Spending intelligence: leakage candidates, subscription totals, bill summary.
- Today Mode: upcoming obligation alerts.

## 4.8 Finance Rollup Tables

Following the two-tier analytics model from v6 Section 4.7. These are Derived, not Temporal. Temporal = what happened. Derived = what it means.

*▶ [Rev3 CHANGE] Weekly rollups and portfolio rollups added. Four-table rollup model.*

**finance_daily_rollups:**

user_id, date, net_worth, liquid_net_worth, total_assets, total_liabilities, daily_income, daily_expenses, daily_net_cashflow, investment_value. All NUMERIC(15,2). Refreshed on transaction insert/update (event-driven).

**finance_weekly_rollups:**

*▶ [Rev3 NEW] Weekly rollup table for variance detection and habit-oriented comparisons.*

user_id, week_start_date, week_end_date, total_income, total_expenses, net_cashflow, savings_rate, top_expense_categories (JSONB), category_variance_flags (JSONB), net_worth_start, net_worth_end, net_worth_delta. Refreshed nightly.

**finance_monthly_rollups:**

user_id, month, net_worth_start, net_worth_end, net_worth_change, total_income, total_expenses, savings_rate, top_expense_categories (JSONB), investment_return, goal_contributions (JSONB). Refreshed nightly.

**portfolio_rollups:**

*▶ [Rev3 NEW] Portfolio rollup table separating market movement from cash movement.*

user_id, period_date, period_type (daily, monthly), account_id, total_value, total_cost_basis, unrealized_gain, realized_gain_period, dividend_income_period, deposits_period, withdrawals_period, market_movement (total_value change - deposits + withdrawals), concentration_top_holding (JSONB). Refreshed nightly.

## 4.9 Cross-Domain Intelligence

Because accounts and financial goals live in the graph alongside journal entries, tasks, and goals, Personal OS can compute correlations no standalone finance app can:

|**Insight**               |**Sources**                                     |**Classification (D-04)**      |
|--------------------------|------------------------------------------------|-------------------------------|
|Spending vs mood          |financial_transactions + journal_nodes.mood     |Correlational: Pattern detected|
|Income vs productivity    |financial_transactions + task_execution_events  |Correlational                  |
|Financial stress indicator|High expense anomalies + low mood + missed tasks|Recommendation: Suggestion     |
|Goal alignment            |Financial goal progress + general goal progress |Descriptive                    |

These are Phase C+ computations, but the data model supports them from day one because finance participates in the graph.

## 4.10 Forecasting Engine

*▶ [Rev3 NEW] Formal forecasting specification.*

|**Forecast**             |**Definition**                                                                                            |**Inputs**                                               |**UI Surface**                                       |
|-------------------------|----------------------------------------------------------------------------------------------------------|---------------------------------------------------------|-----------------------------------------------------|
|Month-end cash forecast  |Project ending balance using known recurring obligations, income events, and recent discretionary behavior|Transactions, recurring_patterns, balance_snapshots      |Overview insight panel, Today Mode (if risk detected)|
|Goal completion forecast |Estimate completion date using actual contribution trend, not aspirational target only                    |goal_allocations, balance_snapshots, contribution history|Goal detail, financial goal nudge                    |
|Burn rate forecast       |Estimate how long current liquid cash can support present spending patterns                               |Liquid net worth, monthly_expenses                       |Overview, Today Mode (if < 3 months runway)          |
|Contribution gap forecast|Monthly amount needed to recover an off-track goal                                                        |target_amount, current_amount, deadline                  |Goal detail, Monthly Review                          |

All forecasts use the DerivedExplanation schema. Forecasts are recomputable and never source of truth. They are Derived outputs that feed the Alerts Engine and Behavioral surfaces.

## 4.11 Anomaly Detection

*▶ [Rev3 NEW] Formal anomaly detection specification.*

|**Anomaly Type**   |**Definition**                                                                           |**Detection Method**                                                                  |
|-------------------|-----------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
|Transaction anomaly|Amount materially exceeds the typical range for that category or merchant                |Individual transaction > 3x category median                                           |
|Category anomaly   |Current category spend materially exceeds rolling median                                 |Current period spend > 1.5x rolling 3-month average                                   |
|Flow anomaly       |Income arrives late, known recurring expense missing, or transfer behavior breaks pattern|Requires recurring_patterns (deferred). Until then, uses simple date-based heuristics.|
|Balance anomaly    |Computed balance diverges from reconciled expectations                                   |ABS(computed - reconciled) > 5% of reconciled balance                                 |

Each anomaly produces a DerivedAlertCandidate (see Section 5.1) with type, severity, entity references, and DerivedExplanation.

# 5. Behavioral Layer: Finance Workflows

These workflows orchestrate financial behavior. They act on Core, consume Derived, and produce Temporal records. The key principle: finance extends existing workflows rather than creating parallel ones.

## 5.1 Alerts Engine

*▶ [Rev3 NEW] Hybrid Derived + Behavioral alerts system.*

The Alerts Engine is the primary bridge between financial intelligence and user action. It materializes high-value Derived signals into stateful objects with lifecycle management.

**Architecture: Derived-First + Behavioral Persistence**

**Derived Layer (computation):**

Anomaly detection, spending spike analysis, recurring subscription detection, and forecast risk functions each produce DerivedAlertCandidate objects:

DerivedAlertCandidate { type, severity (high/medium/low), entity_refs (account_id, transaction_id, goal_id), explanation (DerivedExplanation), score, dedup_key }

These are pure Derived outputs — fully recomputable, no persistence.

**Behavioral Layer (lifecycle):**

The Behavioral layer materializes candidates into stateful alerts:

**finance_alerts**

|**Column**       |**Type**         |**Description**                                                              |
|-----------------|-----------------|-----------------------------------------------------------------------------|
|id               |UUID (PK)        |Primary key                                                                  |
|user_id          |UUID (FK → users)|Owner                                                                        |
|alert_type       |ENUM             |See alert type taxonomy below                                                |
|severity         |ENUM             |high, medium, low                                                            |
|status           |ENUM             |active, dismissed, snoozed, resolved                                         |
|entity_refs      |JSONB            |Referenced entities: { account_id?, transaction_id?, goal_id?, category_id? }|
|dedup_key        |TEXT             |Deduplication key to prevent repeat alerts for same signal                   |
|first_detected_at|TIMESTAMPTZ      |When alert was first materialized                                            |
|last_seen_at     |TIMESTAMPTZ      |Last time the underlying Derived signal was still active                     |
|snoozed_until    |TIMESTAMPTZ NULL |Resume date for snoozed alerts                                               |
|dismissed_at     |TIMESTAMPTZ NULL |When user dismissed                                                          |
|resolved_at      |TIMESTAMPTZ NULL |When underlying condition resolved                                           |
|explanation      |JSONB            |DerivedExplanation snapshot at materialization time                          |
|created_at       |TIMESTAMPTZ      |Record creation                                                              |
|updated_at       |TIMESTAMPTZ      |Last modification                                                            |

*Key design principle: This table is NOT the source of truth — it is a stateful projection of Derived signals.*

**Alert Type Taxonomy**

**Rule-based (MVP):**

|**Alert Type**         |**Trigger**                                                           |**Default Severity**|
|-----------------------|----------------------------------------------------------------------|--------------------|
|low_cash_runway        |Projected month-end cash < user-defined threshold                     |high                |
|large_transaction      |Transaction > 3x category median                                      |medium              |
|uncategorized_aging    |Uncategorized transactions older than 3 days                          |low                 |
|duplicate_import       |Potential duplicate detected during import                            |medium              |
|stale_pending          |Pending transactions older than 7 days                                |low                 |
|goal_off_track         |Financial goal projected to miss deadline at current contribution rate|high                |
|unreconciled_divergence|Computed balance diverges > 5% from last reconciled snapshot          |medium              |
|broken_transfer        |transfer_group_id with count != 2                                     |medium              |

**Pattern-based (Phase 3+, requires recurring_patterns):**

|**Alert Type**       |**Trigger**                                                    |**Default Severity**|
|---------------------|---------------------------------------------------------------|--------------------|
|subscription_detected|New recurring pattern identified with high confidence          |low                 |
|spend_creep          |Category spend increasing across consecutive periods           |medium              |
|impulse_cluster      |Cluster of unplanned discretionary transactions in short window|medium              |
|income_irregularity  |Expected income pattern missed or amount varies significantly  |high                |
|missed_obligation    |Expected recurring payment did not occur on schedule           |high                |
|portfolio_drift      |Asset concentration exceeds threshold                          |medium              |

**Alert Lifecycle**

- Detection loop (Behavioral job): Derived functions compute alert candidates → deduplicate via dedup_key → upsert into finance_alerts. Existing active alerts with the same dedup_key update last_seen_at instead of creating duplicates.
- Auto-resolution: If a subsequent detection loop no longer produces the candidate, the alert’s status transitions to resolved and resolved_at is set. The underlying condition has passed.
- User actions: dismiss (sets dismissed_at, stops resurfacing), snooze (sets snoozed_until, hides until date), resolve (explicit user closure).
- Personalization (Phase 3+): Track dismiss patterns per alert_type. If a user consistently dismisses a specific type, lower its default severity for that user.

**Alert Routing (Three-Tier Model)**

|**Severity**|**Routing**                                                          |**Attention Budget**                                                        |
|------------|---------------------------------------------------------------------|----------------------------------------------------------------------------|
|High        |Today Mode (counts toward U-01: max 2 unsolicited intelligence items)|Earns attention through existing P4 (goal nudges) or P1 (due tasks) channels|
|Medium      |Finance Review Queue (within Cleanup System)                         |Surfaces during financial review workflow or dedicated finance cleanup      |
|Low         |Finance module only (passive insight)                                |Visible in finance module, does not compete for attention outside finance   |

Every alert provides: a primary action, a secondary dismissal/snooze action, and a short explanation of why it surfaced (from DerivedExplanation snapshot).

## 5.2 Transaction Capture Workflows

**Manual Entry**

Quick-add form: account, amount, type, category (from financial_categories), date. Minimal friction. Defaults to most recently used account. Date defaults to today. Status defaults to posted. On save: creates financial_transactions row + financial_transaction_history row (change_type=create), triggers async balance recomputation.

**CSV Import**

Upload CSV, column mapping UI (save mapping per account for future imports), dedup via UNIQUE(account_id, external_id), preview before commit, bulk insert on confirm. Auto-generate balance_snapshots if balance column present.

**API Sync (post-MVP)**

Plaid/SnapTrade integration as a Behavioral service. Runs on schedule or user trigger. Produces transactions with source = api_sync, status = pending (upgraded to posted on confirmation), and external_id for dedup. Append-only, consistent with T-02.

## 5.3 Balance Snapshot Workflow

**Manual:**

User enters current balance for an account. Simple form: account, balance, date. Can mark as reconciled.

**Computed:**

Background job runs nightly. For accounts with transaction history but no snapshot for today, computes balance from last reconciled snapshot + sum of signed_amount (posted/settled only) since then. Saves with source = computed. Never overwrites reconciled snapshots.

## 5.4 Financial Review Workflows

Finance becomes an optional section within existing review workflows, not separate workflows.

**Weekly Financial Review (within Weekly Review)**

*▶ [Rev3 CHANGE] Weekly review now references finance_weekly_rollups and active alerts.*

- What changed this week in net worth, liquid cash, and spending? (from finance_weekly_rollups)
- Which categories were above or below the normal weekly pattern? (category_variance_flags)
- Which transactions remain uncategorized, unreconciled, or suspicious? (from finance_alerts with status = active)
- Did the user fund priority goals at the expected pace? (goal_allocations + balance_snapshots)
- Did finance create stress signals that correlate with missed tasks or low-mood journal entries? (Cross-domain, Phase C+)

Output feeds into weekly_snapshots.notes.

**Monthly Financial Review (within Monthly Review)**

- Month-end net worth and liquid net worth change (from finance_monthly_rollups).
- Savings rate and top category variances versus prior month and three-month baseline.
- Goal progress delta and estimated completion date (from goal progress + forecasting engine).
- Investment performance split into market movement, deposits/withdrawals, and realized gains (from portfolio_rollups).
- Recommended adjustments: reduce category leakage, raise contribution amount, reconcile stale balances, or rebalance a portfolio. All classified as Recommendations (D-04) and dismissible.

## 5.5 Today Mode Integration

Finance participates in Today Mode within the existing attention budget (Invariant U-02: 10 items max). Finance never gets its own section. It surfaces through existing sections when relevant:

|**Existing Section**  |**Finance Integration**                                                   |**Example**                                                     |
|----------------------|--------------------------------------------------------------------------|----------------------------------------------------------------|
|Due/overdue tasks (P1)|Tasks linked to accounts or financial goals                               |Review credit card statement, Transfer $500 to savings          |
|Goal nudges (P4)      |Financial goal progress and projections from Alerts Engine (high severity)|House fund is 73% to target. $850/mo needed to hit deadline.    |
|AI Briefing           |Financial anomalies as briefing bullets from Alerts Engine                |Dining spending this week is 2x your average: $340 vs usual $160|

No new Today Mode sections. No new priority tiers. Finance earns attention through existing channels. Subject to Invariant U-01: max 2 unsolicited intelligence items.

*▶ [Rev3 CHANGE] Today Mode finance items now sourced from Alerts Engine routing, not ad hoc Derived queries.*

**Recommended Today Mode Finance Blocks**

*▶ [Rev3 NEW] Specific Today Mode finance block definitions.*

|**Block**              |**Trigger**                                            |**Primary Action**               |**Data Source**                                                  |
|-----------------------|-------------------------------------------------------|---------------------------------|-----------------------------------------------------------------|
|Cash safety warning    |Projected month-end cash < user-defined threshold      |Review transactions or move funds|Alerts Engine (low_cash_runway)                                  |
|Goal contribution nudge|On-track probability drops below target                |Transfer now / adjust plan       |Alerts Engine (goal_off_track)                                   |
|Anomaly alert          |Category spend or transaction amount breaches threshold|Inspect / categorize / dismiss   |Alerts Engine (large_transaction, spend_creep)                   |
|Upcoming obligation    |Bill or recurring expense due soon                     |Mark paid / fund account / snooze|Alerts Engine (missed_obligation) + recurring_patterns (deferred)|

## 5.6 Financial Cleanup

Extends the existing Cleanup System with finance-specific review queues. Queues are populated from finance_alerts with medium severity:

|**Queue**                 |**Trigger (Alert Type)**                   |**Action Options**                           |
|--------------------------|-------------------------------------------|---------------------------------------------|
|Uncategorized transactions|uncategorized_aging                        |Categorize, bulk categorize, dismiss         |
|Stale accounts            |is_active = true but no activity in 90 days|Deactivate, update balance, snooze           |
|Unreconciled balances     |unreconciled_divergence                    |Reconcile, add adjustment transaction, snooze|
|Broken transfers          |broken_transfer                            |Fix pairing, void orphan, dismiss            |
|Pending transactions      |stale_pending                              |Post, void, snooze                           |
|Duplicate imports         |duplicate_import                           |Merge, keep both, void duplicate             |

## 5.7 Capture Integration

**Cmd+K financial capture:**

Typing $ or a number triggers financial quick-capture. Parsed as a transaction with amount pre-filled. Creates inbox_item if ambiguous, or directly creates financial_transactions row if parseable.

**Source connections:**

Source items (investment articles, financial advice) link to accounts or financial goals via captured_for edges. Memory nodes (financial decisions) link via semantic_reference.

## 5.8 AI Modes: Finance Extensions

|**Mode**|**Finance Extension**                                      |**Example Query**                   |
|--------|-----------------------------------------------------------|------------------------------------|
|Ask     |Queries financial_transactions with filters                |What did I spend on dining in March?|
|Plan    |Creates financial goals, suggests contributions            |Help me plan saving for a house     |
|Reflect |Pulls Derived cashflow into narrative                      |How was my spending this month?     |
|Improve |Surfaces category trends, anomalies, and leakage candidates|Where can I cut spending?           |

**New retrieval mode added:**

|**Mode**    |**Type Weights**                               |**Recency**|**Status Filter**|
|------------|-----------------------------------------------|-----------|-----------------|
|financial_qa|account: 1.0, goal(financial): 0.8, memory: 0.4|90 days    |Active accounts  |

# 6. UX → System Mapping

*▶ [Rev3 NEW] Screen-to-layer-to-data-source mapping for implementation clarity.*

Every screen and block maps to a primary layer, secondary layer, and concrete data source. This mapping ensures implementation decisions are grounded in the architecture.

|**Screen / Block**               |**Primary Layer**|**Secondary Layer**|**Main Data Source**                                      |**Key Requirements**                                             |
|---------------------------------|-----------------|-------------------|----------------------------------------------------------|-----------------------------------------------------------------|
|Overview hero (net worth + trend)|Derived          |Temporal           |balance_snapshots, exchange_rates, daily rollups          |Liquid net worth toggle, trend explanation, period comparison    |
|Overview cashflow cards          |Derived          |Temporal           |Transactions, monthly rollups                             |Explanation text, pending-vs-posted treatment, forecast access   |
|Overview insights panel          |Behavioral       |Derived            |Alerts Engine outputs, forecasts, category patterns       |Primary decision surface, not decorative. Actions + explanations.|
|Accounts list                    |Core             |Derived            |Account nodes, current balance cache, reconciliation state|Account health state, quick reconcile action                     |
|Account detail                   |Core             |Temporal           |Transactions, snapshots, transfers                        |Balance history, reconciliation markers, upcoming obligations    |
|Transactions list                |Temporal         |Behavioral         |financial_transactions, categories, import status         |Bulk categorize, split, recurring detection, audit-friendly state|
|Transaction detail sheet         |Temporal         |Derived            |Single transaction + category baseline + merchant history |Why flagged, comparison to normal                                |
|Holdings list                    |Temporal         |Derived            |Holdings snapshots, market prices, investment_transactions|Performance attribution, concentration warnings                  |
|Holdings detail                  |Derived          |Temporal           |Trade history, valuation history, allocation data         |Return drivers, benchmark comparison, allocation context         |
|Goal progress card               |Core             |Derived            |goal_allocations, balances, contribution history          |Actionable: transfer, adjust target, revise deadline             |
|Today Mode finance item          |Behavioral       |Derived            |Alerts Engine outputs (high severity)                     |One clear action + explanation per item                          |

# 7. Screen-Specific Recommendations

*▶ [Rev3 NEW] Product-level screen recommendations from review.*

## 7.1 Overview

- Keep the current dashboard foundation, but add an Insights Panel immediately below the hero instead of relying only on charts.
- Split descriptive metrics from action metrics. Example: Net worth is descriptive; “you need to move $350 this week to stay on track” is action-oriented.
- Support period switchers that change not only the chart but also the narrative explanation below it.
- Include a visible distinction between total net worth and liquid net worth.

## 7.2 Accounts

- Show reconciliation state directly in the list: current, stale, needs review, or disconnected.
- Account detail should include balance history, pending transaction total, and upcoming obligations tied to that account.
- Credit accounts should show utilization and statement due context, not just balance.

## 7.3 Transactions

- Stronger workflow support: bulk categorize, bulk ignore, merge duplicates, mark as transfer, mark recurring, and fix broken imports.
- Add state chips for pending, posted, settled, imported, suspicious, and uncategorized beyond type-coloring.
- Filters should include account, category, merchant, status, tags, amount range, and date range.

## 7.4 Holdings

- Performance explanation: what changed because of market movement versus contributions (from portfolio_rollups).
- Concentration and diversification warnings when a holding or sector becomes too dominant (from portfolio_drift alert type).
- Brokerage accounts should support liquid vs illiquid treatment where relevant to the wider system.

# 8. Implementation Roadmap

The finance module is phased to deliver standalone value at each step, layering intelligence on top of proven data capture.

*▶ [Rev3 CHANGE] Roadmap updated to incorporate Alerts Engine, weekly/portfolio rollups, and deferred schemas. Phase structure revised per review priorities.*

## 8.1 Finance Phase 1: Foundation + Capture (2 weeks)

**Core:**

account_nodes table, goal_nodes extension (goal_type, target_amount, current_amount, currency), financial_categories table with system-seeded defaults, goal_allocations table, account_funds_goal edge relation with type-pair constraints.

**Temporal:**

financial_transactions table (with status field), balance_snapshots table (with reconciliation fields), financial_transaction_history table for audit trail.

**Behavioral:**

Manual entry form, CSV import (column mapping, saved mappings per account, dedup via external_id, preview before commit), basic balance snapshot workflow.

**Views:**

Account list, transaction list per account, balance history.

*Why this phase matters:*

Without a trustworthy data model, later intelligence will be noisy and untrustworthy.

## 8.2 Finance Phase 2: Intelligence + Decision Surfaces (2 weeks)

**Temporal:**

investment_holdings table, investment_transactions table, exchange_rates table.

**Derived:**

Net worth computation (with multi-currency via exchange_rates), liquid net worth, cashflow analytics, spending category breakdown (hierarchical), financial goal progress (via allocations), market_prices cache.

**Rollups:**

finance_daily_rollups, finance_weekly_rollups, finance_monthly_rollups, portfolio_rollups.

**Alerts Engine (MVP rule-based):**

finance_alerts table. Detection loop for rule-based alerts: low_cash_runway, large_transaction, uncategorized_aging, duplicate_import, stale_pending, goal_off_track, unreconciled_divergence, broken_transfer. Three-tier routing.

*▶ [Rev3 CHANGE] Alerts Engine moved from Phase 3 to Phase 2. Decision surfaces are the module’s identity.*

**Views:**

Net worth over time chart, monthly cashflow chart, spending by category (with hierarchy drill-down), portfolio composition, Overview insights panel with active alerts.

*Why this phase matters:*

This is where the module becomes Personal OS-native. Intelligence and alerts transform it from a dashboard into a behavior engine.

## 8.3 Finance Phase 3: Behavioral Integration + Patterns (2 weeks)

**Behavioral:**

Today Mode integration (finance items sourced from Alerts Engine high-severity routing), Weekly/Monthly Review financial sections, Financial cleanup queues (populated from Alerts Engine medium-severity), AI mode financial extensions (Ask, Plan, Reflect, Improve with financial context), Cmd+K financial quick-capture.

**Deferred schemas activated:**

counterparty_entities table (Core Configuration), recurring_patterns table (Derived). Counterparty resolution flow activated. Recurring pattern detection algorithm deployed.

**Pattern-based alerts activated:**

subscription_detected, spend_creep, impulse_cluster, income_irregularity, missed_obligation, portfolio_drift.

**Spending intelligence upgraded:**

Merchant concentration (using counterparty_entities), leakage candidates (using recurring_patterns), forecasting engine (month-end cash, goal completion, burn rate, contribution gap).

*Why this phase matters:*

This creates durable differentiation versus standard finance dashboards. Pattern detection and cross-system integration are unique to Personal OS.

## 8.4 Finance Phase 4: Advanced (post-MVP)

- Bank/broker API sync (Plaid, SnapTrade).
- Computed balance snapshots (nightly job with reconciliation respect).
- Investment performance metrics (simple return, dividend tracking).
- Cross-domain intelligence (mood vs spending, productivity vs income).
- Lot-level cost basis tracking for realized gains (using investment_transactions.lot_id).
- Budget/spending plan configuration.
- Projected cashflow and retirement planning.
- Behavioral finance intelligence (impulse detection, regret tagging, waste scoring).
- Alert personalization (dismiss-pattern learning, severity adjustment).

# 9. Finance Invariants

These extend the v6 Invariants Appendix (Section 13). Referenced by ID throughout this document.

**F-01: Transactions Never Become Nodes**

Financial transactions are Temporal records. They never participate in the graph as nodes or edges. Accounts are the bridge between financial behavior and the semantic graph.

**F-02: Amount Sign Convention**

financial_transactions.amount is always positive. Direction is encoded in transaction_type. signed_amount is a PostgreSQL generated column. Application code must never store negative amounts.

**F-03: Financial Goal Field Consistency**

For goals with goal_type = financial: target_amount and currency must be non-null. For goals with goal_type = general: target_amount, current_amount, and currency must all be null. Enforced at application layer.

**F-04: Balance Snapshot Uniqueness**

At most one balance_snapshot per account_id per snapshot_date. Enforced by UNIQUE constraint.

**F-05: Transfer Pairing**

Every transfer_in must have a corresponding transfer_out with the same transfer_group_id. Exactly 2 records per group. Orphans flagged by cleanup.

**F-06: No Shadow Graph**

Account-to-goal relationships are represented exclusively via account_funds_goal edges. No denormalized ID arrays or reference fields on companion tables.

**F-07: Cashflow Exclusion Rule**

Transfer and investment transaction types are excluded from cashflow calculations (income/expense totals, savings rate, burn rate). They represent internal movement.

**F-08: Transaction Status in Balance**

Balance computations must only include transactions where status IN (posted, settled) unless explicitly computing projected/pending balances.

**F-09: Reconciliation Authority**

Computed balances must never override reconciled snapshots. A balance_snapshot with is_reconciled = true is user-verified truth.

**F-10: Historical FX Immutability**

Historical net worth calculations always use the exchange rate from the snapshot date (via exchange_rates table), not the current date.

**F-11: Financial Audit Trail**

Every mutation to a financial_transaction row must produce a corresponding financial_transaction_history row. Append-only, never modified or deleted.

**F-12: Category Referential Integrity**

financial_transactions.category_id must reference a valid financial_categories row. Category deletion is blocked if transactions reference it.

**F-13: Goal Allocation Bounds**

For percentage allocations: SUM of all allocation values for a single account across all goals must not exceed 1.0.

**F-14: Alert Deduplication**

The Alerts Engine must deduplicate candidates via dedup_key before upserting into finance_alerts. Duplicate signals update last_seen_at, not create new rows.

**F-15: Alert Source of Truth**

finance_alerts is a stateful projection of Derived signals, not a source of truth. The underlying Derived computation is authoritative. Alerts may be purged and regenerated.

**F-16: Recurring Pattern Confidence Threshold**

Recurring patterns with confidence < 0.5 are not surfaced to users. Patterns with confidence 0.5–0.7 are surfaced as suggestions. Patterns > 0.7 are auto-classified.

*▶ [Rev3 CHANGE] Invariants F-14, F-15, F-16 are new. Cover Alerts Engine and Recurring Patterns.*

# 10. Design Decisions Log (Finance)

Key architectural decisions for the finance module. Extends Section 12 of the v6 architecture document.

**10.1 Hybrid Layer Model**

Accounts and financial goals are Core (graph-participating). Transactions and holdings are Temporal (non-graph). Insights are Derived. This prevents graph pollution while enabling cross-domain intelligence.

**10.2 Extended goal_nodes vs Separate financial_goal_nodes**

Financial goals are modeled by extending goal_nodes with nullable financial fields rather than creating a separate companion table. Preserves unified status lifecycle, analytics, and edge logic.

**10.3 Positive Amount + Generated signed_amount**

Canonical amount is always positive. Transaction direction encoded in transaction_type. signed_amount is a PostgreSQL GENERATED ALWAYS AS column. Eliminates sign-confusion bugs.

**10.4 Snapshot-Based Holdings**

Investment holdings are point-in-time snapshots, not running state. This follows the Wealthfolio/Ghostfolio model: append snapshots, derive performance.

**10.5 Finance Extends Existing Workflows**

Finance integrates into existing Today Mode, Weekly/Monthly Reviews, AI Modes, and Cleanup rather than creating parallel workflows. Respects attention budget (U-01, U-02).

**10.6 No Edge for funding_account_ids**

Account-to-goal relationships are represented exclusively via account_funds_goal edges. Shadow graph pattern rejected.

**10.7 Data Ingestion: Manual-First**

MVP uses manual entry + CSV import only. Bank/broker API sync deferred to post-MVP.

**10.8 Hierarchical Categories (Rev2)**

Structured financial_categories table with parent_id hierarchy replaces free-text. Enables consistent aggregation and drill-down analytics.

**10.9 Goal Allocation Model (Rev2)**

goal_allocations table with percentage and fixed allocation types replaces binary account-to-goal. Prevents double-counting.

**10.10 Transaction Status Lifecycle (Rev2)**

pending/posted/settled status models real-world transaction lifecycle. Prevents double-counting of unconfirmed transactions.

**10.11 Reconciliation Model (Rev2)**

balance_snapshots gains is_reconciled flag. Reconciled snapshots are authoritative; computed balances never override them.

**10.12 Financial Audit Trail (Rev2)**

financial_transaction_history table for immutable change tracking. Financial data has higher auditability requirements.

**10.13 Multi-Currency via Historical Rates (Rev2)**

exchange_rates table stores historical FX rates. Net worth calculations always use rates from snapshot date.

**10.14 Investment Transactions (Rev2)**

Separate investment_transactions table for asset-level activity. Enables future lot tracking and corporate action handling.

**10.15 Alerts Engine: Hybrid Derived + Behavioral (Rev3)**

Alerts are Derived-first (computed signals) with Behavioral persistence (stateful lifecycle management). The finance_alerts table is a projection, not a source of truth. This keeps the system compliant with the four-layer architecture while enabling stateful alert management, three-tier routing, and personalization.

**10.16 Counterparty Entities: Specified, Deferred (Rev3)**

Full schema designed now for forward compatibility. Implementation deferred to Phase 3. Without it, spending intelligence operates on raw strings. With it, merchant normalization enables accurate concentration analysis, recurring detection, and default categorization.

**10.17 Recurring Patterns: Specified, Deferred (Rev3)**

Full schema and detection algorithm designed now. Implementation deferred to Phase 3. Feeds the Alerts Engine (missed obligations, subscription detection), cashflow forecasting, and spending intelligence (leakage candidates). Without this, these capabilities operate on simpler heuristics.

**10.18 Four-Table Rollup Model (Rev3)**

Daily, weekly, monthly, and portfolio rollups replace the two-table model. Weekly rollups support variance detection and habit-oriented comparisons. Portfolio rollups separate market movement from cash movement. Both are critical for review workflows and performance explanation.

**10.19 Alerts Engine in Phase 2, Not Phase 3 (Rev3)**

Decision surfaces are the module’s identity. Moving the Alerts Engine to Phase 2 ensures the finance module is Personal OS-native from its second iteration, not a dashboard that gets intelligence bolted on later.

# 11. Revision History

|**Revision**|**Date**  |**Summary of Changes**                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
|------------|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|Rev1        |April 2026|Initial finance module design. Core entities, Temporal tables, basic Derived intelligence, behavioral integration.                                                                                                                                                                                                                                                                                                                                                                |
|Rev2        |April 2026|Added: transaction status lifecycle, reconciliation model, hierarchical categories, goal allocations, audit trail, investment transactions, exchange rates, multi-currency support. 12 review items applied.                                                                                                                                                                                                                                                                      |
|Rev3        |April 2026|Added: Alerts Engine (hybrid Derived + Behavioral with finance_alerts table and three-tier routing), counterparty_entities (specified, deferred), recurring_patterns (specified, deferred), finance_weekly_rollups and portfolio_rollups, forecasting engine spec, anomaly detection spec, UX-to-system mapping, screen-specific recommendations. Roadmap restructured: Alerts Engine moved to Phase 2. 3 new invariants (F-14, F-15, F-16). 5 new design decisions (10.15–10.19).|

*— End of Document —*