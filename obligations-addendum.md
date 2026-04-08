# PERSONAL OS

## Recurring Obligations Feature Addendum

Finance Module Design — Rev4 Addition | April 2026

*Complete specification for recurring financial obligations: subscriptions, bills, utilities, loans, and all predictable recurring outflows. Designed as a two-stage system: Derived detection → Core promotion. Extends the finance module with obligation nodes, breakdowns, seasonal intelligence, and Alerts Engine integration.*

# 1. Architecture Position

Recurring obligations are durable, user-owned commitments to recurring financial outflows. They pass the Core admission test: the user would say “Netflix is one of my bills” or “my electricity bill is one of my things.”

## 1.1 Layer Distribution

|**Layer** |**Obligation Representation**                     |**Examples**                                  |
|----------|--------------------------------------------------|----------------------------------------------|
|Core      |Durable obligation entities in the graph          |obligation_nodes, obligation_breakdowns       |
|Temporal  |Per-occurrence payment events                     |obligation_events                             |
|Derived   |Seasonal profiles, rate change detection, matching|obligation_seasonal_profiles, match candidates|
|Behavioral|Alerts, Today Mode routing, upcoming/missed logic |Alerts Engine extensions, cleanup queues      |

## 1.2 Two-Stage Lifecycle

**Stage 1 — Detection (Derived):** recurring_patterns (Section 4.7 of finance doc) detects patterns from transaction history. Patterns with confidence > 0.7 become promotion candidates.

**Stage 2 — Promotion (Core):** User confirms a detected pattern, or manually creates an obligation. A new obligation node is created in the graph. The Promotion Contract (v6 Section 5.8) applies — provenance edge back to originating pattern, original pattern stays intact with status → user_confirmed.

## 1.3 Governing Constraint

**Constraint 8:** Obligations are Core entities promoted from Derived patterns or manually created. They participate in the graph, link to accounts and goals, and drive Behavioral alerting. Transaction matching emits Temporal events; Derived recomputes from events. Derived never mutates Derived directly.

# 2. Core Layer: Obligation Entities

## 2.1 obligation_nodes (Core Companion Table)

*▶ [Rev4 NEW] New Core entity. Node type “obligation” added to nodes.type ENUM.*

|**Column**            |**Type**                              |**Layer**     |**Description**                                                     |
|----------------------|--------------------------------------|--------------|--------------------------------------------------------------------|
|node_id               |UUID (PK, FK → nodes)                 |Core          |1:1 with nodes                                                      |
|obligation_type       |ENUM                                  |Core          |subscription, utility, rent, loan, insurance, tax, membership, other|
|recurrence_rule       |TEXT                                  |Core          |rrule/cron expression. Same pattern as task_nodes.recurrence.       |
|amount_model          |ENUM                                  |Core          |fixed, variable, seasonal                                           |
|expected_amount       |NUMERIC(15,2) NULL                    |Core          |For fixed: exact. For variable/seasonal: midpoint or typical.       |
|amount_range_low      |NUMERIC(15,2) NULL                    |Core          |Lower bound for variable/seasonal. NULL for fixed.                  |
|amount_range_high     |NUMERIC(15,2) NULL                    |Core          |Upper bound for variable/seasonal. NULL for fixed.                  |
|currency              |TEXT                                  |Core          |ISO 4217                                                            |
|account_id            |UUID (FK → nodes)                     |Core          |Primary account this obligation charges                             |
|counterparty_entity_id|UUID NULL (FK → counterparty_entities)|Core          |Provider link (when activated)                                      |
|category_id           |UUID NULL (FK → financial_categories) |Core          |Default spending category                                           |
|billing_anchor        |SMALLINT NULL                         |Core          |Optional hint: typical day-of-month. Not source of truth.           |
|next_expected_date    |DATE NULL                             |CACHED DERIVED|Computed from recurrence_rule + last obligation_event. See S-01.    |
|status                |ENUM                                  |Core          |active, paused, cancelled                                           |
|autopay               |BOOLEAN DEFAULT false                 |Core          |Whether auto-deducted. Affects alert severity.                      |
|origin                |ENUM                                  |Core          |manual, detected                                                    |
|confidence            |FLOAT NULL                            |Core          |Detection confidence at creation. NULL for manual.                  |
|started_at            |DATE NULL                             |Core          |When obligation began                                               |
|ended_at              |DATE NULL                             |Core          |When cancelled/ended                                                |
|cancellation_url      |TEXT NULL                             |Core          |Direct link to cancel                                               |
|notes                 |TEXT NULL                             |Core          |Additional context                                                  |

## 2.2 obligation_breakdowns (Core Configuration Table)

*▶ [Rev4 NEW] New configuration table. Sub-components of obligations (e.g. base charge, usage, taxes for a utility bill). Not a graph node.*

Breakdowns enable per-component tracking, anomaly detection, and rate change history. They are versioned via effective_from/effective_to — components are never mutated for rate changes.

|**Column**       |**Type**          |**Description**                                                                     |
|-----------------|------------------|------------------------------------------------------------------------------------|
|id               |UUID (PK)         |Primary key                                                                         |
|obligation_id    |UUID (FK → nodes) |Parent obligation node                                                              |
|name             |TEXT              |Display name (e.g. “Usage Charge”, “Delivery Fee”)                                  |
|normalized_name  |TEXT              |Lowercase canonical name for grouping/dedup (e.g. “delivery_fee”)                   |
|component_type   |ENUM              |base, usage, tax, fee, discount, adjustment, other                                  |
|amount_model     |ENUM              |fixed, variable, seasonal, percentage                                               |
|expected_amount  |NUMERIC(15,2) NULL|Typical amount. NULL for percentage-based.                                          |
|amount_range_low |NUMERIC(15,2) NULL|Lower bound for variable/seasonal                                                   |
|amount_range_high|NUMERIC(15,2) NULL|Upper bound for variable/seasonal                                                   |
|percentage_value |NUMERIC(7,4) NULL |For percentage-based: the rate (e.g. 0.0825 for 8.25% tax). NULL for non-percentage.|
|match_keywords   |TEXT[] NULL       |Hints for auto-matching transaction line items (e.g. [“kwh”, “usage”])              |
|effective_from   |DATE              |When this component version became active                                           |
|effective_to     |DATE NULL         |When superseded. NULL = current version.                                            |
|status           |ENUM              |active, deprecated                                                                  |
|sort_order       |INTEGER DEFAULT 0 |Display ordering                                                                    |
|created_at       |TIMESTAMPTZ       |Creation                                                                            |
|updated_at       |TIMESTAMPTZ       |Last modification                                                                   |

## 2.3 New Edge Relations

*▶ [Rev4 NEW] Two new edge relations added to the Edge Type-Pair Constraints table.*

|**Relation**              |**Category**        |**Allowed Source → Target**|**Semantics**                                                |
|--------------------------|--------------------|---------------------------|-------------------------------------------------------------|
|obligation_charges_account|Financial / Workflow|obligation → account       |This obligation is paid from this account                    |
|obligation_impacts_goal   |Financial / Workflow|obligation → goal          |This obligation contributes to or affects this financial goal|

**Why dedicated relations instead of semantic_reference:** obligation → account is structural (drives balance forecasting, alert routing). obligation → goal is causal influence (drives goal progress reasoning, optimization suggestions). Both are too specific and operationally important for the generic semantic_reference relation. G-02 compliance: specific relation exists, so semantic_reference is invalid for these pairs.

## 2.4 Full Graph Connection Map

|**Connection**         |**Edge Relation**         |**Example**                                                  |
|-----------------------|--------------------------|-------------------------------------------------------------|
|Obligation → Account   |obligation_charges_account|Netflix charges my Chase checking                            |
|Obligation → Goal      |obligation_impacts_goal   |Internet bill impacts “Reduce expenses” goal                 |
|Memory → Obligation    |semantic_reference        |Decision to switch providers linked to obligation            |
|Source → Obligation    |captured_for              |Article about ISP comparison captured for internet obligation|
|Journal → Obligation   |journal_reflects_on       |Journal entry reflecting on subscription habits              |
|Obligation → Obligation|semantic_reference        |Bundled services: internet references TV (same provider)     |

## 2.5 semantic_reference Constraints Update

Add obligation ↔ memory, obligation ↔ kb_entry, obligation ↔ obligation to allowed pairs for semantic_reference. Obligation → goal uses obligation_impacts_goal (G-02). Obligation → account uses obligation_charges_account (G-02). Journal already allows journal_entry → any.

# 3. Temporal Layer: Obligation Events

*▶ [Rev4 NEW] New Temporal table. Follows the same pattern as task_execution_events — a per-occurrence record of what happened for each obligation payment cycle.*

## 3.1 obligation_events

|**Column**       |**Type**                               |**Description**                                                      |
|-----------------|---------------------------------------|---------------------------------------------------------------------|
|id               |UUID (PK)                              |Primary key                                                          |
|user_id          |UUID (FK → users)                      |Owner                                                                |
|obligation_id    |UUID (FK → nodes)                      |The obligation                                                       |
|expected_for_date|DATE                                   |The date this payment was expected                                   |
|transaction_id   |UUID NULL (FK → financial_transactions)|Matched transaction, if any                                          |
|event_status     |ENUM                                   |paid, missed, upcoming, skipped                                      |
|match_confidence |FLOAT NULL                             |Confidence of transaction match (0.0–1.0). NULL for manual or missed.|
|occurred_at      |TIMESTAMPTZ NULL                       |When payment actually occurred. NULL for missed/upcoming.            |
|notes            |TEXT NULL                              |Optional context                                                     |
|created_at       |TIMESTAMPTZ                            |Record creation                                                      |

## 3.2 Correct Data Flow

The critical architectural principle: Derived never mutates Derived directly. Transaction matching emits Temporal events, and Derived recomputes from those events.

**1.** Transaction posts → Derived matching computes candidate match with weighted confidence score.

**2.** Match accepted → obligation_events row created (Temporal) with event_status=paid, transaction_id set, match_confidence stored.

**3.** Derived recomputation triggered → next_expected_date on obligation_nodes recalculated from recurrence_rule + latest obligation_event.

**4.** No match by expected date + lead_time → obligation_events row created with event_status=missed → Alerts Engine fires.

## 3.3 Transaction Matching Model

Weighted confidence scoring for transaction-to-obligation matching:

|**Signal**               |**Weight**|**Description**                                |
|-------------------------|----------|-----------------------------------------------|
|counterparty_entity match|0.45      |Normalized merchant identity — strongest signal|
|amount within range      |0.20      |Within expected ±30% or seasonal p25–p75       |
|timing proximity         |0.20      |Within ±5 days of next_expected_date           |
|category match           |0.10      |Same category_id as obligation                 |
|account match            |0.05      |Same account_id (baseline)                     |

**Thresholds:** Auto-link ≥ 0.7. Suggestion 0.4–0.7. Below 0.4: no match. Consistent with F-16 confidence threshold pattern.

# 4. Derived Layer: Seasonal Intelligence

## 4.1 obligation_seasonal_profiles (Derived Cache)

*▶ [Rev4 NEW] New Derived table. Computes seasonal fingerprints for obligations with variable or seasonal amount models.*

|**Column**          |**Type**                              |**Description**                                             |
|--------------------|--------------------------------------|------------------------------------------------------------|
|id                  |UUID (PK)                             |Primary key                                                 |
|obligation_id       |UUID (FK → nodes)                     |The obligation                                              |
|breakdown_id        |UUID NULL (FK → obligation_breakdowns)|Specific component, or NULL for whole-obligation            |
|period_type         |ENUM DEFAULT month                    |month (MVP). Future: week, billing_cycle.                   |
|period_value        |SMALLINT                              |For month: 1–12. For week: 1–52.                            |
|expected_amount     |NUMERIC(15,2)                         |Predicted amount (weighted median)                          |
|p25_amount          |NUMERIC(15,2) NULL                    |25th percentile                                             |
|p75_amount          |NUMERIC(15,2) NULL                    |75th percentile                                             |
|sample_count        |SMALLINT                              |Number of historical data points                            |
|last_sample_at      |TIMESTAMPTZ NULL                      |Most recent data point used                                 |
|confidence          |FLOAT                                 |0.0–1.0. From sample_count, variance stability, recency.    |
|is_seasonal         |BOOLEAN                               |Whether this obligation exhibits seasonal behavior          |
|seasonality_strength|FLOAT NULL                            |(period_median - annual_median) / IQR. NULL if not seasonal.|
|annual_median       |NUMERIC(15,2)                         |Stored annual baseline                                      |
|annual_p25          |NUMERIC(15,2) NULL                    |Annual 25th percentile                                      |
|annual_p75          |NUMERIC(15,2) NULL                    |Annual 75th percentile                                      |
|computed_at         |TIMESTAMPTZ                           |When last computed                                          |

## 4.2 Confidence Calculation

confidence = w1 × min(sample_count / 6, 1.0) + w2 × variance_stability + w3 × recency_score

Where w1=0.4, w2=0.35, w3=0.25. Variance stability = 1 - (coefficient of variation), clamped to [0,1]. Recency score decays from 1.0 based on months since last_sample_at (exponential, half-life = 12 months).

## 4.3 Seasonality Detection Algorithm

**1.** Collect matched transactions over past 24 months, weighted by recency (exponential decay, half-life = 12 months).

**2.** Compute annual baseline: weighted median, p25, p75.

**3.** Group by period. For each period with 2+ data points, compute weighted median and IQR.

**4.** Compute seasonality_strength per period: (period_median - annual_median) / annual_IQR.

**5.** Flag is_seasonal = true if any 2+ consecutive periods show |seasonality_strength| > 0.5.

**6.** Profiles with confidence < 0.5 are not used for alerting (consistent with F-16).

## 4.4 Spike and Rate Change Detection

Three distinct scenarios the system distinguishes:

|**Scenario**     |**Detection**                                           |**Alert**                                          |**Action**                 |
|-----------------|--------------------------------------------------------|---------------------------------------------------|---------------------------|
|One-time spike   |Amount exceeds expected but next month returns to normal|“Internet was $70, expected $50”                   |Review, dismiss if one-time|
|Rate change      |2+ consecutive months at new amount (±5%)               |“Internet increased from $50 to $70 starting March”|Update obligation amount   |
|Seasonal variance|Amount matches seasonal profile                         |“Electricity $190, within July range $170–$200”    |No alert — expected        |

**Rate change detection:** When an obligation alert fires for amount deviation, track persistence. If 2 consecutive months show the same new amount (±5%), classify as probable rate change. Surface as recommendation (D-04): “Your internet bill has been $70 for 2 months. Update expected amount?” If confirmed, obligation updates and relevant breakdowns are versioned (effective_to set, new row created).

## 4.5 Downstream Consumers

|**Consumer**      |**Usage**                                                                               |
|------------------|----------------------------------------------------------------------------------------|
|Anomaly detection |Compare against seasonal profile instead of annual median. Eliminates false positives.  |
|Forecasting engine|Month-end cash forecast uses seasonal profiles for variable obligations.                |
|Alerts Engine     |Seasonally-aware alerting: “July electricity $230 exceeds typical July range $170–$200.”|
|Monthly Review    |“Heating costs entering seasonal peak. Expected +$60/month through February.”           |

# 5. Behavioral Layer: Alerts & Today Mode

## 5.1 New Alert Types

*▶ [Rev4 NEW] Added to the Alerts Engine taxonomy (Section 5.1 of finance doc).*

**Rule-based (activates with obligations):**

|**Alert Type**         |**Trigger**                                             |**Default Severity**          |**Autopay Behavior**             |
|-----------------------|--------------------------------------------------------|------------------------------|---------------------------------|
|upcoming_obligation    |Due within dynamic lead_time, no match yet              |medium (high if autopay=false)|Suppressed to low if autopay=true|
|missed_obligation      |Past expected date, no matching transaction             |high                          |Deferred 5 days if autopay=true  |
|obligation_amount_spike|Matched txn exceeds expected or seasonal profile by >20%|medium                        |Same regardless of autopay       |
|obligation_rate_change |2+ consecutive months at new amount (±5%)               |low                           |Same regardless of autopay       |
|obligation_expiring    |Known end date within 14 days                           |low                           |Same regardless of autopay       |

**Pattern-based (Phase 3+):**

|**Alert Type**          |**Trigger**                                                     |**Default Severity**|
|------------------------|----------------------------------------------------------------|--------------------|
|obligation_creep        |Total obligation spend increasing across 3+ consecutive months  |medium              |
|obligation_concentration|Single provider >40% of total obligation spend                  |low                 |
|obligation_optimization |Similar obligations at lower market rates (requires source data)|low                 |

## 5.2 Dynamic Lead Time

Replace static 3-day window with dynamic lead time calculation:

lead_time = base_lead_time × adjustments. Base = 3 days. Adjustments: autopay=true → reduce to 1 day. Historical variance > 2 days → extend by variance. Account balance < expected amount → extend to 5 days (future). Clamped to [1, 7] days. Computed on each detection loop, never stored.

## 5.3 Today Mode Routing

Obligations surface through existing Today Mode channels. No new sections or priority tiers.

|**Alert Severity**                 |**Today Mode Surface**   |**Example**                                                             |
|-----------------------------------|-------------------------|------------------------------------------------------------------------|
|High (missed, upcoming non-autopay)|P1: Due/overdue tasks    |“Internet bill ($70) is 2 days overdue. No payment detected.”           |
|High (goal impact)                 |P4: Goal nudges          |“Subscription spend $45 over monthly target for ‘Reduce expenses’ goal.”|
|Medium                             |Does not enter Today Mode|Surfaces in Finance Review Queue during cleanup                         |
|Low                                |Does not enter Today Mode|Passive insight in finance module only                                  |

All subject to U-01 (max 2 unsolicited intelligence items) and U-02 (10-item Today Mode cap).

## 5.4 Context Layer Behavior

When viewing an obligation in the detail pane, the context layer shows (following v6 Section 9.2 priority order):

**1.** Backlinks: goals, memories, sources referencing this obligation.

**2.** Outgoing: account it charges, related obligations (bundles).

**3.** Provenance: if promoted from detected pattern, link to originating recurring_pattern.

**4.** Activity: recent matched transactions (last 3), next expected date, rate change history.

**5.** AI suggestions: related obligations to bundle or compare.

All within 8-item context layer cap (U-03).

# 6. Invariants

*▶ [Rev4 NEW] New invariants extending Section 9 of the finance module doc.*

**F-17: Obligation Amount Model Consistency**

For amount_model = fixed: expected_amount must be non-null, amount_range_low/high must be null. For variable/seasonal: range fields must be non-null.

**F-18: Obligation Status Lifecycle**

Obligations with status = cancelled must have ended_at set. Obligations with status = active must have ended_at = null.

**F-19: next_expected_date Is Derived**

next_expected_date is CACHED DERIVED (S-01). Source of truth is recurrence_rule + last obligation_event from obligation_events.

**F-20: Breakdown Amount Model Consistency**

For component amount_model = percentage: percentage_value must be non-null and expected_amount must be null. For fixed/variable/seasonal: the inverse.

**F-21: One Active Breakdown Version**

At most one active version per (obligation_id, normalized_name) where effective_to IS NULL. Enforced by partial unique index.

**F-22: Deprecated Breakdown Has End Date**

Components with status = deprecated must have effective_to set.

**F-23: Seasonal Confidence Threshold**

Seasonal profiles with confidence < 0.5 are excluded from anomaly detection and forecasting. May be stored but not surfaced.

**F-24: Seasonality Requires Consecutive Deviation**

is_seasonal requires 2+ consecutive periods with |seasonality_strength| > 0.5. Single-month deviations do not qualify.

**F-25: Obligation Event Uniqueness**

At most one terminal obligation event (paid, missed, skipped) per obligation per expected_for_date. Mirrors S-04.

**F-26: Obligation Event Ownership**

obligation_events.user_id must match the owner_id of the referenced obligation node. T-04 alignment.

# 7. Indexes

**obligation_breakdowns:**

(obligation_id) — fetch all components for an obligation

(component_type) — cross-obligation analytics

(effective_from, effective_to) — historical range queries

Partial unique: (obligation_id, normalized_name) WHERE effective_to IS NULL — enforces F-21

**obligation_events:**

(obligation_id, expected_for_date) — lookup and uniqueness enforcement

(user_id, expected_for_date) — “what’s due this week” queries

(transaction_id) WHERE transaction_id IS NOT NULL — reverse lookup from transaction

**obligation_seasonal_profiles:**

(obligation_id, period_type, period_value) — seasonal lookup

(obligation_id, breakdown_id) — per-component profiles

# 8. Roadmap Placement

## 8.1 Finance Phase 2 Additions

obligation_nodes table and node type. obligation_breakdowns table. obligation_charges_account and obligation_impacts_goal edge relations with type-pair constraints. Manual obligation creation form. Rule-based obligation alerts (upcoming, missed, spike, rate change, expiring).

## 8.2 Finance Phase 3 Additions

obligation_events table (Temporal). Transaction-to-obligation matching with weighted confidence. obligation_seasonal_profiles (Derived). Seasonality detection algorithm. Rate change detection. Promoted-from-pattern workflow (two-stage lifecycle). Pattern-based alerts (creep, concentration, optimization). Breakdown-level anomaly detection.

# 9. Design Decisions

*▶ [Rev4 NEW] Extending Section 10 of the finance module doc.*

**10.20 Obligations as Core Entities (Rev4)**

Recurring obligations pass the Core admission test — users say “this is one of my bills.” They are durable, linkable, and the user manages them over time. Behavioral-only tracking would break long-term because obligations need graph participation for cross-domain intelligence.

**10.21 Two-Stage Detection → Promotion (Rev4)**

Follows the same pattern as source items: Derived detection surfaces candidates, user confirms to promote to Core. Consistent with Promotion Contract (v6 Section 5.8). Provenance preserved.

**10.22 Dedicated Edge Relations for Obligations (Rev4)**

obligation_charges_account and obligation_impacts_goal are dedicated relations, not semantic_reference. The account relationship is structural (drives forecasting). The goal relationship is causal influence (drives optimization). G-02 compliance.

**10.23 recurrence_rule Over Frequency ENUM (Rev4)**

Uses rrule/cron text field matching task_nodes.recurrence pattern. Avoids ENUM inflexibility and maintains consistency across the system.

**10.24 Versioned Breakdowns (Rev4)**

Breakdowns use effective_from/effective_to versioning instead of mutation. Preserves full rate change history. Enables trend analysis and rate change detection at the component level.

**10.25 Temporal Events as Matching Intermediary (Rev4)**

Transaction matching emits obligation_events (Temporal), then Derived recomputes. Derived never mutates Derived directly. This maintains correct layer separation and provides an audit trail of payment history.

**10.26 Seasonal Intelligence as Derived Cache (Rev4)**

Seasonal profiles are fully Derived — computed from transaction history, purgeable, recomputable. They eliminate false positive alerts for known seasonal variation and improve forecasting accuracy.

**10.27 Weighted Confidence Matching (Rev4)**

Transaction-to-obligation matching uses weighted signal scoring (counterparty 0.45, amount 0.20, timing 0.20, category 0.10, account 0.05). Auto-link ≥ 0.7, suggestion 0.4–0.7. Consistent with F-16 confidence thresholds.