# PERSONAL OS — Unified Alerts System Addendum

**Architecture v6 Addendum | April 2026 | Revision 2**

Derived → Behavioral Alert Materialization Contract  
Cross-Domain Alerts with Lifecycle, Routing, and Suppression

**Supersedes:** `finance_alerts` (finance-module-design-rev3 § 5.1), `snooze_records` (v6 § 3.5), finance Alerts Engine Phase 2 sequencing (finance-module-design-rev3 § Roadmap)

-----

## Table of Contents

1. [Motivation](#1-motivation)
1. [Architectural Position](#2-architectural-position)
1. [AlertCandidate Contract](#3-alertcandidate-contract)
1. [Producer Contract](#4-producer-contract)
1. [Behavioral Layer: Alerts Table](#5-behavioral-layer-alerts-table)
1. [Alert Type Taxonomy](#6-alert-type-taxonomy)
1. [Severity Precedence & Routing](#7-severity-precedence--routing)
1. [Suppression & Cooldown](#8-suppression--cooldown)
1. [Detection Loop Architecture](#9-detection-loop-architecture)
1. [Entity Deletion & Orphan Handling](#10-entity-deletion--orphan-handling)
1. [Migration & Supersession](#11-migration--supersession)
1. [Settings Integration](#12-settings-integration)
1. [v6 Architecture Impact](#13-v6-architecture-impact)
1. [Invariants](#14-invariants)
1. [Roadmap Placement](#15-roadmap-placement)
1. [Revision History](#16-revision-history)

-----

## 1. Motivation

The finance module (Rev3) introduced the Alerts Engine: a hybrid Derived + Behavioral system that materializes computed signals into stateful objects with lifecycle management, three-tier severity routing, dedup, and personalization. This is the most mature intelligence-to-action pipeline in Personal OS.

However, non-finance domains (tasks, goals, KB, sources) rely on ephemeral Derived flags for the same conceptual need. Stale content detection produces flags that surface in Cleanup queues but have no persistence, no dismiss/snooze lifecycle, no dedup, and no auto-resolution. The only stateful piece is `snooze_records`, which is detached from the signal that triggered the snooze.

This creates three inconsistencies:

**Lifecycle gap:** A snoozed finance alert auto-resolves when the condition clears. A snoozed stale task resurfaces on a timer regardless of whether the user acted on it.

**Learning gap:** Finance tracks dismiss patterns and adjusts severity. Other domains have no equivalent. The system cannot learn that a user consistently ignores stale KB warnings.

**Routing gap:** Finance routes through a formal three-tier model (Today Mode / Cleanup / Module-only). Other domains use ad hoc query-time computation with no shared routing contract.

This addendum extracts the materialization contract from finance and generalizes it as a cross-domain architectural primitive. The goal is not to make everything an alert — it is to provide a single, principled pipeline from Derived signal to user-facing action surface.

-----

## 2. Architectural Position

### 2.1 The Core Primitive: Alert Materialization Contract

The real abstraction is not “a shared alerts table.” It is a formal contract between the Derived and Behavioral layers:

- **Derived Layer** produces `AlertCandidate` objects — pure, recomputable, stateless signal descriptions.
- **Behavioral Layer** materializes candidates into Alerts — stateful projections with lifecycle, routing, and personalization.

This is a Derived → Behavioral materialization contract. Finance already implements it. This addendum makes it a system-wide primitive.

### 2.2 What Is NOT an Alert

Not every signal should become an alert. Alerts are reserved for system-detected anomalies, staleness, and risk signals — conditions where the system has identified something that warrants user attention but the user has not explicitly requested it.

**These are NOT alerts:**

- Due tasks — expected behavior, surfaced in Today Mode P1 via direct query.
- Scheduled reviews — planned workflow triggers, not anomaly detection.
- User-created reminders — explicit user commitments, managed through task system.
- Morning commit suggestions — AI briefing content, not lifecycle-managed signals.

**These ARE alerts:**

- A task untouched for 14 days (stale detection).
- A goal with no progress for 30 days (drift detection).
- Projected month-end cash below safety threshold (financial risk).
- A decision whose `review_at` date has passed (resurfacing trigger).
- KB entry not linted in 90 days (content decay).

### 2.3 Layer Classification

|Component                |Layer                     |Rationale                                                                                       |
|-------------------------|--------------------------|------------------------------------------------------------------------------------------------|
|AlertCandidate production|Derived                   |Pure computation from Core + Temporal. Recomputable. No persistence.                            |
|`alerts` table           |Behavioral                |Stateful projection with two row classes (see § 5.2). Not source of truth for active conditions.|
|Detection loop (job)     |Behavioral                |Orchestration code that triggers Derived computation and materializes results.                  |
|Routing engine           |Behavioral                |Determines which surface receives each alert based on severity + domain quotas.                 |
|`alert_preferences`      |Behavioral                |Suppression scores from dismiss-pattern learning. Behavioral adaptation.                        |
|Alert settings           |Settings (Typed + Dynamic)|Thresholds and toggles. Core configuration per settings addendum.                               |

### 2.4 Alert Row Duality: Projections vs. History

▶ **[Rev2 NEW]** The `alerts` table contains two classes of rows with different recomputation semantics:

**Projection-state rows** (`status = active` or `snoozed`): These represent current or deferred system-detected conditions. They are regenerable from the detection loop plus current Core/Temporal state. Deleting all projection-state rows and re-running detection must reproduce an equivalent active set. The projection claim applies to the alert’s active condition model, not to the full lifecycle history stored on the row (e.g., `first_detected_at` is preserved metadata, not part of the recomputable signal).

**Behavioral-history rows** (`status = dismissed`, `resolved`, or `auto_resolved`): These represent user or system interaction history. They record that a specific alert was acted upon and are retained as behavioral audit records. They are not expected to be reconstructed purely by recomputation — the user’s dismiss action or the system’s auto-resolution event is the source of truth. These rows follow standard Behavioral retention (indefinite, user-owned interaction history).

Both classes share the same table, same schema, and same lifecycle state machine. The distinction is semantic, not physical: projection rows are disposable if the detection loop can regenerate them; history rows are not.

-----

## 3. AlertCandidate Contract

### 3.1 AlertCandidate Schema

Every domain producer emits candidates conforming to this interface. This is the formal Derived → Behavioral handoff contract.

|Field               |Type              |Required|Description                                                                                                      |
|--------------------|------------------|--------|-----------------------------------------------------------------------------------------------------------------|
|`alert_type`        |TEXT              |Yes     |Namespaced type: `domain.signal_name` (e.g., `finance.low_cash_runway`, `tasks.stale_todo`)                      |
|`domain`            |TEXT              |Yes     |Producer domain: `finance`, `tasks`, `goals`, `kb`, `sources`, `decisions`                                       |
|`severity`          |ENUM              |Yes     |`high`, `medium`, `low`. Producer’s recommended severity.                                                        |
|`entity_refs`       |JSONB             |Yes     |Standardized: `{ primary: { type, id }, related: [{ type, id }] }`                                               |
|`explanation`       |DerivedExplanation|Yes     |D-01 compliant. `summary` + `factors[]`.                                                                         |
|`score`             |FLOAT             |No      |Signal confidence (0.0–1.0). Used for ranking within severity tier.                                              |
|`dedup_key`         |TEXT              |Yes     |Logical grouping key for deduplication. Constructed per producer’s declared canonical dimensions (see § 4.2).    |
|`source_hash`       |TEXT              |Yes     |Exact signal identity. SHA-256 of canonical inputs. Enables change detection vs. repeat detection.               |
|`detection_cycle_id`|UUID              |Yes     |Links to the specific detection run for debuggability and explainability audits.                                 |
|`today_mode_channel`|TEXT              |No      |Preferred Today Mode channel if routed to high severity: `due_overdue`, `goal_nudge`, `review_prompt`. See § 7.2.|

▶ **[Addendum NEW]** `source_hash` and `detection_cycle_id` are new fields not present in finance Rev3. `source_hash` distinguishes “same condition persisting” from “condition changed.” `detection_cycle_id` enables lineage tracing.

▶ **[Rev2 NEW]** `today_mode_channel` added so producers declare which existing Today Mode section their alert should render in, rather than relying on a standalone alert slot.

### 3.2 entity_refs Standardized Shape

The `entity_refs` JSONB field uses a standardized structure for consistent UI handling, predictable joins, and future graph bridging:

```json
{ "primary": { "type": "task", "id": "<uuid>" }, "related": [{ "type": "goal", "id": "<uuid>" }] }
```

- `primary` (required): The single entity this alert is most about. Drives the primary action and detail navigation.
- `related` (optional array): Supporting entities that provide context. Displayed as secondary links.

Valid types are governed by a code-side registry of node and configuration entity types, not a static prose list. The registry must include at minimum: `task`, `goal`, `account`, `transaction`, `category`, `kb_entry`, `source`, `memory`, `decision`, `obligation`. New types are added by registering them in code; this document provides examples, not an exhaustive enumeration.

▶ **[Rev2 CHANGE]** Valid types are now registry-governed rather than a static list. Prevents the document from drifting behind the wider architecture as new Core types are added.

### 3.3 alert_type Naming Convention

`alert_type` uses TEXT with domain-prefixed naming instead of ENUM. This avoids migration overhead when new alert types are added and aligns with the registry-driven architecture direction from the settings system.

**Format:** `domain.signal_name`

**Enforcement:**

- Code-side registry validates all `alert_type` values at producer registration.
- Database CHECK constraint enforces prefix format: `CHECK (alert_type ~ '^[a-z]+\.[a-z_]+$')`.
- Unknown `alert_type` values are rejected at materialization, not silently stored.

▶ **[Addendum CHANGE]** Replaces the ENUM approach from finance Rev3 § 5.1. Existing finance alert types migrate: `low_cash_runway` → `finance.low_cash_runway`, etc.

-----

## 4. Producer Contract

▶ **[Rev2 NEW]** This section defines the operational contract that all domain producers must satisfy. Without these rules the architecture is elegant on paper but prone to inconsistent implementations.

### 4.1 Snapshot Semantics

**Default: Full-snapshot producers.** Every producer must emit the complete current set of active `AlertCandidate` objects for its scope on each detection cycle. The detection loop uses absence of a candidate (no matching `dedup_key` in this cycle’s output) as the auto-resolution signal. This is the simplest and most robust model.

**Exception: Delta-mode producers.** Producers explicitly registered as expensive or incrementally maintained may emit only new or changed candidates. Delta-mode requires:

- Explicit registration in the producer registry with `mode = 'delta'`.
- A reconciliation path: the producer must provide an equivalent mechanism for the detection loop to determine which previously-active alerts are no longer valid. This may be an explicit “still-active” heartbeat set, a “resolved” candidate emission, or a periodic full-snapshot reconciliation cycle (e.g., weekly full sweep alongside nightly deltas).
- Without a reconciliation path, delta mode is not permitted. Stale alerts that cannot auto-resolve violate A-02.

### 4.2 Dedup Key Construction Rules

Every producer must declare its canonical dedup dimensions in the producer registry. The `dedup_key` is a deterministic string constructed from these dimensions. Different alert types within the same domain may have different dedup dimensions.

**Construction rule:** `dedup_key = alert_type + ":" + sorted(dimension=value) pairs`, joined by `|`. The exact serialization format is defined in code; what matters architecturally is that every producer declares which dimensions constitute identity for its alert type.

**Examples:**

|Alert Type                 |Canonical Dedup Dimensions    |Example dedup_key                                  |
|---------------------------|------------------------------|---------------------------------------------------|
|`tasks.stale_todo`         |task_id                       |`tasks.stale_todo:task=<uuid>`                     |
|`tasks.stale_in_progress`  |task_id                       |`tasks.stale_in_progress:task=<uuid>`              |
|`tasks.blocked_cluster`    |goal_id (root of subtree)     |`tasks.blocked_cluster:goal=<uuid>`                |
|`finance.low_cash_runway`  |account_id, forecast_window   |`finance.low_cash_runway:account=<uuid>|window=30d`|
|`finance.large_transaction`|transaction_id                |`finance.large_transaction:txn=<uuid>`             |
|`goals.stale_goal`         |goal_id                       |`goals.stale_goal:goal=<uuid>`                     |
|`goals.drift_detected`     |goal_id                       |`goals.drift_detected:goal=<uuid>`                 |
|`kb.duplicate_detected`    |sorted(entry_id_a, entry_id_b)|`kb.duplicate_detected:pair=<uuid_a>|<uuid_b>`     |
|`decisions.review_due`     |decision_id                   |`decisions.review_due:decision=<uuid>`             |

**Registry requirement:** A producer that emits an `alert_type` without a registered dedup dimension declaration is rejected at startup. This is a hard contract, not a convention.

### 4.3 Producer Dependencies

Producers may depend on:

- **Core tables** (nodes, companion tables, edges): Always permitted.
- **Temporal tables** (transactions, execution events, etc.): Always permitted.
- **Derived caches** (rollups, computed scores): Permitted, but producers must tolerate stale or missing caches gracefully. A missing Derived cache must not cause the producer to crash or emit incorrect candidates — it should either skip the alert type or fall back to a direct computation.

Producers must NOT:

- Write directly to the `alerts` table. All materialization goes through the detection loop.
- Depend on other producers’ output. No cross-producer dependencies. Each producer operates independently on Core + Temporal + (optionally) Derived state.
- Perform mutations on Core or Temporal data. Producers are read-only observers.

### 4.4 Idempotency

A producer invoked twice in the same detection cycle with the same underlying data must produce the same set of candidates (same `dedup_key` values, same `source_hash` values). Non-deterministic producers (e.g., those depending on LLM output) must pin their source_hash to the inputs, not the outputs, so that repeated invocations with unchanged inputs produce stable dedup behavior.

### 4.5 Producer Classification: Entity-State vs. Aggregate

▶ **[Rev2 NEW]** Alert types fall into two producer classes with different lifecycle characteristics:

**Entity-state alerts** monitor a single entity’s condition. They are stable: the alert persists as long as the entity’s state meets the trigger condition, and auto-resolves when it doesn’t. Examples: `tasks.stale_todo`, `goals.stale_goal`, `finance.low_cash_runway`, `decisions.review_due`.

**Aggregate/system alerts** detect patterns across multiple entities or contextual conditions. They may churn: the alert can appear and disappear across cycles as the surrounding context shifts, even without user action. Examples: `tasks.blocked_cluster`, `kb.duplicate_detected`, `finance.impulse_cluster`, `sources.capture_backlog`.

**Lifecycle implications:**

- Entity-state alerts use tight dedup (single entity ID). Auto-resolution is clean: entity state changes → candidate disappears → alert auto-resolves.
- Aggregate alerts use composite dedup keys. Producers should apply stability thresholds before emitting candidates — e.g., `tasks.blocked_cluster` should require the cluster to persist for 2+ consecutive cycles before materialization, to prevent churn. The `score` field should reflect confidence that the pattern is stable.
- The producer registry must declare which class each alert type belongs to. This classification affects UI presentation (entity-state alerts link to a single entity; aggregate alerts show a summary with multiple entity links) and dedup/resolution behavior.

-----

## 5. Behavioral Layer: Alerts Table

### 5.1 alerts Schema

Single unified table replacing `finance_alerts` and absorbing `snooze_records`. This table is a Behavioral projection — not a source of truth for active conditions. It contains both projection-state rows and behavioral-history rows (see § 2.4).

|Column              |Type             |Description                                                                                                 |
|--------------------|-----------------|------------------------------------------------------------------------------------------------------------|
|`id`                |UUID (PK)        |Primary key                                                                                                 |
|`user_id`           |UUID (FK → users)|Owner                                                                                                       |
|`alert_type`        |TEXT             |Namespaced: `domain.signal_name`. `CHECK (~ '^[a-z]+\.[a-z_]+$')`                                           |
|`domain`            |TEXT             |Producer domain. Redundant with `alert_type` prefix for query convenience. CHECK consistency enforced.      |
|`severity`          |ENUM             |`high`, `medium`, `low`. Effective severity after precedence chain (see § 7.1).                             |
|`original_severity` |ENUM             |Producer’s recommended severity, before any adjustments. Immutable after materialization.                   |
|`status`            |ENUM             |`active`, `dismissed`, `snoozed`, `resolved`, `auto_resolved`                                               |
|`entity_refs`       |JSONB            |Standardized: `{ primary: { type, id }, related: [{ type, id }] }`                                          |
|`dedup_key`         |TEXT             |Deduplication key. UNIQUE per user + active status.                                                         |
|`source_hash`       |TEXT             |Exact signal identity from candidate. Enables versioning.                                                   |
|`detection_cycle_id`|UUID             |Links to producing detection run.                                                                           |
|`producer_class`    |TEXT             |`entity_state` or `aggregate`. Set at materialization from producer registry.                               |
|`today_mode_channel`|TEXT NULL        |Preferred Today Mode channel from producer. NULL for medium/low severity alerts that don’t enter Today Mode.|
|`first_detected_at` |TIMESTAMPTZ      |When alert was first materialized.                                                                          |
|`last_seen_at`      |TIMESTAMPTZ      |Last time Derived signal was still active.                                                                  |
|`snoozed_until`     |TIMESTAMPTZ NULL |Resume date for snoozed alerts.                                                                             |
|`dismissed_at`      |TIMESTAMPTZ NULL |When user dismissed.                                                                                        |
|`resolved_at`       |TIMESTAMPTZ NULL |When user explicitly resolved or auto-resolution triggered.                                                 |
|`explanation`       |JSONB            |DerivedExplanation snapshot at materialization time.                                                        |
|`routing_snapshot`  |JSONB NULL       |Last routing decision metadata (see § 7.3).                                                                 |
|`created_at`        |TIMESTAMPTZ      |Record creation.                                                                                            |
|`updated_at`        |TIMESTAMPTZ      |Last modification.                                                                                          |

▶ **[Addendum NEW]** Fields not in finance Rev3: `domain`, `original_severity`, `source_hash`, `detection_cycle_id`, `auto_resolved` status value.

▶ **[Rev2 NEW]** Fields added in Rev2: `producer_class`, `today_mode_channel`, `routing_snapshot`.

▶ **[Addendum CHANGE]** `snooze_records` (v6 § 3.5) is absorbed. Snooze is now `status = snoozed` + `snoozed_until` on this table. See Section 11 (Migration).

### 5.2 Key Indices

- `UNIQUE(user_id, dedup_key) WHERE status = 'active'` — prevents duplicate active alerts for same signal.
- `INDEX(user_id, domain, status)` — domain-scoped queries.
- `INDEX(user_id, severity, status) WHERE status = 'active'` — routing engine queries.
- `INDEX(user_id, status, snoozed_until) WHERE status = 'snoozed'` — snooze expiry scan.

### 5.3 Status Lifecycle

Alert status follows a state machine with these valid transitions:

|From           |To             |Trigger                                       |Side Effects                                                               |
|---------------|---------------|----------------------------------------------|---------------------------------------------------------------------------|
|(new)          |`active`       |Materialization from candidate                |`first_detected_at`, `last_seen_at` set                                    |
|`active`       |`dismissed`    |User action                                   |`dismissed_at` set. Row becomes behavioral history.                        |
|`active`       |`snoozed`      |User action                                   |`snoozed_until` set                                                        |
|`active`       |`resolved`     |User explicit resolution                      |`resolved_at` set. Row becomes behavioral history.                         |
|`active`       |`auto_resolved`|Detection loop no longer produces candidate   |`resolved_at` set. Row becomes behavioral history.                         |
|`snoozed`      |`active`       |`snoozed_until` reached + signal still present|`snoozed_until` cleared                                                    |
|`snoozed`      |`auto_resolved`|`snoozed_until` reached + signal gone         |`resolved_at` set, `snoozed_until` cleared. Row becomes behavioral history.|
|`dismissed`    |(terminal)     |No further transitions                        |—                                                                          |
|`resolved`     |(terminal)     |No further transitions                        |—                                                                          |
|`auto_resolved`|(terminal)     |No further transitions                        |—                                                                          |

▶ **[Addendum NEW]** `auto_resolved` is a new terminal status distinguishing system resolution from user resolution. This supports analytics: “how many alerts resolved themselves vs. required user action?”

-----

## 6. Alert Type Taxonomy

### 6.1 Finance Domain (migrated from Rev3)

All existing finance alert types are migrated with domain prefix. Behavior unchanged.

|Alert Type                       |Trigger                                            |Default Severity|
|---------------------------------|---------------------------------------------------|----------------|
|`finance.low_cash_runway`        |Projected month-end cash < threshold               |high            |
|`finance.large_transaction`      |Transaction > 3x category median                   |medium          |
|`finance.uncategorized_aging`    |Uncategorized transactions > 3 days old            |low             |
|`finance.duplicate_import`       |Potential duplicate detected during import         |medium          |
|`finance.stale_pending`          |Pending transactions > 7 days old                  |low             |
|`finance.goal_off_track`         |Financial goal projected to miss deadline          |high            |
|`finance.unreconciled_divergence`|Computed vs. reconciled balance > 5%               |medium          |
|`finance.broken_transfer`        |`transfer_group_id` with count ≠ 2                 |medium          |
|`finance.subscription_detected`  |New recurring pattern (Phase 3+)                   |low             |
|`finance.spend_creep`            |Category spend increasing across periods (Phase 3+)|medium          |
|`finance.impulse_cluster`        |Cluster of unplanned discretionary spend (Phase 3+)|medium          |
|`finance.income_irregularity`    |Expected income missed or varied (Phase 3+)        |high            |
|`finance.missed_obligation`      |Expected recurring payment missed (Phase 3+)       |high            |
|`finance.portfolio_drift`        |Asset concentration exceeds threshold (Phase 3+)   |medium          |

### 6.2 Tasks Domain

▶ **[Addendum NEW]** Tasks domain alert types. Thresholds sourced from `task_settings` typed table.

|Alert Type               |Trigger                                                                                                              |Default Severity|Producer Class|
|-------------------------|---------------------------------------------------------------------------------------------------------------------|----------------|--------------|
|`tasks.stale_todo`       |Todo task untouched > `stale_todo_days` (default 14)                                                                 |low             |entity-state  |
|`tasks.stale_in_progress`|In-progress task untouched > `stale_in_progress_days` (default 7)                                                    |medium          |entity-state  |
|`tasks.blocked_cluster`  |3+ tasks stale in same goal subtree (requires goal edges). Must persist 2+ consecutive cycles before materialization.|medium          |aggregate     |

### 6.3 Goals Domain

▶ **[Addendum NEW]** Goals domain alert types. Thresholds sourced from `task_settings` typed table.

|Alert Type               |Trigger                                                           |Default Severity|Producer Class|
|-------------------------|------------------------------------------------------------------|----------------|--------------|
|`goals.stale_goal`       |Active goal with no progress > `stale_goal_days` (default 30)     |medium          |entity-state  |
|`goals.milestone_overdue`|Goal milestone past expected completion (requires milestone dates)|medium          |entity-state  |
|`goals.drift_detected`   |Goal momentum score declining for 2+ consecutive weeks            |high            |entity-state  |

### 6.4 Knowledge Base Domain

▶ **[Addendum NEW]** KB domain alert types. Thresholds sourced from `kb_settings` typed table.

|Alert Type             |Trigger                                                         |Default Severity|Producer Class|
|-----------------------|----------------------------------------------------------------|----------------|--------------|
|`kb.stale_entry`       |Accepted KB entry not linted > `stale_kb_days` (default 90)     |low             |entity-state  |
|`kb.duplicate_detected`|Embedding similarity > `dedup_similarity_cutoff` between entries|low             |aggregate     |

### 6.5 Sources Domain

▶ **[Addendum NEW]** Sources domain alert types. Thresholds sourced from `kb_settings` typed table.

|Alert Type                  |Trigger                                                     |Default Severity|Producer Class|
|----------------------------|------------------------------------------------------------|----------------|--------------|
|`sources.unprocessed_raw`   |Raw source unprocessed > `stale_source_raw_days` (default 7)|low             |entity-state  |
|`sources.unclassified_inbox`|Inbox item pending > `stale_inbox_days` (default 3)         |low             |entity-state  |
|`sources.capture_backlog`   |5+ unprocessed sources accumulated                          |medium          |aggregate     |

### 6.6 Decisions Domain

▶ **[Addendum NEW]** Decision resurfacing unified into the alerts system. Replaces the standalone query in v6 § 5.7.

|Alert Type                        |Trigger                                        |Default Severity|Producer Class|
|----------------------------------|-----------------------------------------------|----------------|--------------|
|`decisions.review_due`            |Decision `review_at` date has passed (user-set)|medium          |entity-state  |
|`decisions.outcome_missing_short` |Decision with no outcome after 7 days          |low             |entity-state  |
|`decisions.outcome_missing_medium`|Decision with no outcome after 30 days         |medium          |entity-state  |
|`decisions.outcome_missing_long`  |Decision with no outcome after 90 days         |high            |entity-state  |

-----

## 7. Severity Precedence & Routing

▶ **[Rev2 NEW]** This section consolidates severity resolution and routing into a single, explicit model.

### 7.1 Severity Precedence Chain

Severity is determined by a monotonic-downward chain. No step in the chain may upgrade severity — only preserve or downgrade. This ensures severity always means “how serious is this condition?” and never drifts into “how much attention capacity exists today?”

**Chain (applied in order):**

1. **Producer severity** → The `original_severity` recommended by the domain producer. Immutable after materialization.
1. **User override** → Per-alert-type severity override from EAV settings (`alerts.<type>.severity_override`). If set, replaces producer severity. Can only be `high`, `medium`, or `low`. User override is the only mechanism that can set severity higher than producer recommendation, and it is an explicit user choice.
1. **Suppression downgrade** → If `alert_preferences.suppression_score` exceeds `suppression_threshold_downgrade`, effective severity drops one tier. If it exceeds `suppression_threshold_mute`, the alert type is muted (not materialized). See § 8.
1. **Routing placement** → The routing engine determines which surface receives the alert based on effective severity + domain quotas + attention budget caps. Routing may hold, defer, or redirect an alert to a lower-attention surface, but it does not modify the severity value stored on the alert row. Routing is a placement decision, not a severity decision.

The `severity` column on the `alerts` row stores the result of steps 1–3. Routing (step 4) affects where the alert appears, not what severity it carries.

### 7.2 Today Mode Routing: Existing Channels, Not a Unified Slot

▶ **[Rev2 CHANGE]** High-severity alerts earn placement through existing Today Mode sections. There is no standalone alert section or dedicated alert slot. This preserves the v6 Today Mode philosophy where Today Mode is a behavior engine, not a generic inbox.

**Routing model:**

- Routing logic is centralized in the alerts engine (Behavioral layer).
- Rendering is mapped into existing Today Mode sections.
- Each alert type declares a preferred `today_mode_channel` in the producer registry:
  - `due_overdue` → renders in P1 (due/overdue tasks section).
  - `goal_nudge` → renders in P4 (goal nudges section).
  - `review_prompt` → renders in the review/reflection section.
- The routing engine respects existing per-section caps from `today_mode_settings`. An alert that would exceed a section cap is held in the domain’s review queue until a slot opens.

|Effective Severity|Routing Target                                                                                           |Attention Budget                                                               |
|------------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------|
|High              |Today Mode via declared channel (P1/P4/review). Counts toward U-01: max 2 unsolicited intelligence items.|Subject to per-section caps and U-02 (10-item hard cap).                       |
|Medium            |Cleanup System review queues (domain-specific).                                                          |Surfaces during cleanup workflow or dedicated domain review.                   |
|Low               |Domain module only (passive insight).                                                                    |Visible within originating module. Does not compete for cross-domain attention.|

**Engine-level attention enforcement:**

- U-01 enforcement: The routing engine surfaces at most `max_unsolicited_items` (default 2, from `today_mode_settings`) high-severity alerts to Today Mode per day. Excess high-severity alerts remain active but are held in the domain’s review queue until a slot opens.
- U-02 enforcement: Alert slots in Today Mode count toward the 10-item hard cap. If the cap is nearly full from due tasks and focus items, alerts are suppressed to lower-tier surfaces.
- Per-domain high-severity cap: 1 high-severity alert per domain in Today Mode. No single domain monopolizes the attention budget.
- Per-domain medium-severity cap: 5 active medium-severity alerts per domain in Cleanup queues (configurable). Excess alerts queued internally.

**Ranking within tier:** When multiple alerts compete for a slot, ranking uses: (1) severity, (2) score (signal confidence), (3) `first_detected_at` (oldest first). Domain quotas are applied after ranking.

### 7.3 Routing State & Explainability

▶ **[Rev2 NEW]** Each routing cycle writes a `routing_snapshot` on affected alert rows. This is a JSONB object containing:

```json
{
  "routed_to": "today_mode",
  "channel": "goal_nudge",
  "routed_at": "2026-04-09T06:00:00Z",
  "cycle_id": "<detection_cycle_uuid>",
  "reason": "highest_severity_in_domain",
  "held_reason": null
}
```

For alerts held back from their preferred surface:

```json
{
  "routed_to": "cleanup",
  "channel": null,
  "routed_at": "2026-04-09T06:00:00Z",
  "cycle_id": "<detection_cycle_uuid>",
  "reason": "domain_quota_exceeded",
  "held_reason": "finance domain already has 1 high-severity alert in Today Mode"
}
```

This enables the system to answer “why didn’t I see this alert today?” in settings or debug UI. The `routing_snapshot` is overwritten each routing cycle (not append-only) — it reflects the most recent routing decision only. Historical routing decisions are not retained; the `detection_cycles` telemetry table provides aggregate observability.

-----

## 8. Suppression & Cooldown

### 8.1 alert_preferences Table

Behavioral adaptation table that tracks user responses to alert types and adjusts effective severity.

|Column                       |Type             |Description                                                                          |
|-----------------------------|-----------------|-------------------------------------------------------------------------------------|
|`id`                         |UUID (PK)        |Primary key                                                                          |
|`user_id`                    |UUID (FK → users)|Owner                                                                                |
|`alert_type`                 |TEXT             |Namespaced alert type (matches `alerts.alert_type`)                                  |
|`suppression_score`          |FLOAT            |0.0 (no suppression) to 1.0 (fully suppressed). Computed from dismiss history.       |
|`total_dismissed`            |INTEGER DEFAULT 0|Lifetime dismiss count for this alert type.                                          |
|`total_resolved`             |INTEGER DEFAULT 0|Lifetime user-resolved count.                                                        |
|`total_auto_resolved`        |INTEGER DEFAULT 0|Lifetime auto-resolved count.                                                        |
|`effective_severity_override`|ENUM NULL        |If `suppression_score` exceeds threshold, severity is downgraded. NULL = no override.|
|`cooldown_until`             |TIMESTAMPTZ NULL |If set, alerts of this type are suppressed until this time.                          |
|`updated_at`                 |TIMESTAMPTZ      |Last modification.                                                                   |

### 8.2 Suppression Algorithm

- On each dismiss: increment `total_dismissed`, recompute `suppression_score`.
- `suppression_score` formula: `dismissed / (dismissed + resolved + auto_resolved)`, with recency weighting (exponential decay, half-life = 90 days on dismiss events).
- If `suppression_score > suppression_threshold_downgrade` (default 0.70): `effective_severity_override` drops one tier (`high → medium`, `medium → low`).
- If `suppression_score > suppression_threshold_mute` (default 0.90): alert type is effectively muted (`low → suppressed`, not materialized).
- User can explicitly override via settings: “Always show” / “Never show” per `alert_type`.

### 8.3 Suppression Scope Limitation

▶ **[Rev2 NEW]** v1 suppression operates at `alert_type` granularity only. This is intentionally coarse. Dismissing `tasks.stale_todo` suppresses all stale task alerts, even though the user may only dislike them for low-value chores and still want them for strategic work. The same limitation applies to finance: dismissing many `finance.large_transaction` alerts for a noisy account suppresses them for all accounts.

This is an acknowledged v1 limitation, not a design oversight. Future versions may support scoped suppression by producer-defined context (e.g., account, category, entity subtype, or domain segment). Scoped suppression would likely live in a separate table rather than overloading `alert_preferences`, but that design is deferred until usage patterns from v1 suppression clarify which scoping dimensions matter most.

### 8.4 Cooldown Mechanism (Severity-Aware)

▶ **[Rev2 CHANGE]** Cooldown is now severity-aware. The v1 universal “3 dismissals in 7 days → 30-day cooldown” rule was too aggressive for medium and high-severity alert types, where the consequence of missing a signal is higher.

**Cooldown eligibility rules:**

- **Low-severity alert types:** Eligible for automatic cooldown. When a user dismisses `cooldown_trigger_count` (default 3) alerts of the same type within `cooldown_window_days` (default 7), a `cooldown_duration_days` (default 30) cooldown is automatically applied.
- **Medium-severity alert types:** Eligible for automatic cooldown only if the producer opts in by setting `cooldown_eligible = true` in the producer registry. Default is not eligible.
- **High-severity alert types:** Never eligible for automatic cooldown. The user can still manually mute via “Never show” override in settings, but the system will not auto-suppress based on dismiss patterns.

During cooldown, new candidates of the affected type are not materialized. Cooldown is visible in settings and overridable. Invariant A-09 applies: users must never be unaware that alert types are being suppressed.

-----

## 9. Detection Loop Architecture

### 9.1 Detection Cycle

The detection loop is a Behavioral job (ARQ worker) that orchestrates Derived computation and materializes results. Each run is identified by a `detection_cycle_id` (UUID).

**Cycle steps:**

1. **Invoke domain producers:** Each registered producer computes `AlertCandidate` objects from current Core + Temporal state. Full-snapshot producers emit all current candidates; delta producers emit changes plus reconciliation data (see § 4.1).
1. **Deduplicate:** Match candidates to existing active alerts via `dedup_key`. Same `dedup_key` + different `source_hash` = update (condition changed). Same `dedup_key` + same `source_hash` = touch `last_seen_at` only.
1. **Apply suppression:** Check `alert_preferences`. Skip candidates whose `alert_type` is in cooldown or muted. Apply severity downgrade for suppressed types.
1. **Materialize:** New candidates → INSERT into `alerts`. Changed candidates → UPDATE `explanation`, `source_hash`, `last_seen_at`.
1. **Auto-resolve:** Active alerts whose `dedup_key` was NOT produced in this cycle (for full-snapshot producers) or explicitly marked resolved (for delta producers) → `status = auto_resolved`, `resolved_at = now()`.
1. **Orphan check:** Active alerts whose `entity_refs.primary` references a hard-deleted Core node → `status = auto_resolved`, `resolved_at = now()`. See § 10.
1. **Unsnooze:** Snoozed alerts with `snoozed_until < now()`: if signal still present in candidates → `status = active`; if signal absent → `status = auto_resolved`.
1. **Route:** Apply severity precedence chain (§ 7.1), then routing placement (§ 7.2). Write `routing_snapshot` on affected rows.
1. **Log cycle:** Record `detection_cycle` metadata (producer count, candidates produced, materialized, auto_resolved, duration) for observability.

### 9.2 Detection Frequency

|Domain      |Default Frequency                    |Trigger                 |Rationale                                                                                             |
|------------|-------------------------------------|------------------------|------------------------------------------------------------------------------------------------------|
|Finance     |On transaction insert + nightly sweep|Event-driven + scheduled|Transactions are the primary signal source. Nightly catches time-based signals (staleness, forecasts).|
|Tasks       |Nightly                              |Scheduled               |Staleness is day-granularity. No benefit to sub-daily detection.                                      |
|Goals       |Nightly                              |Scheduled               |Progress changes are infrequent. Weekly rollup already captures momentum.                             |
|KB / Sources|Nightly                              |Scheduled               |Content decay is slow. Daily detection is sufficient.                                                 |
|Decisions   |Nightly                              |Scheduled               |`review_at` and outcome windows are date-based.                                                       |

All scheduled detection runs execute as ARQ background jobs with B-04 ownership scoping (same user context as interactive requests).

**Decision resurfacing latency note:** ▶ **[Rev2 NEW]** Decision resurfacing transitions from query-at-load-time (v6 § 5.7) to nightly-materialized alerts. This is a deliberate latency tradeoff: a decision that becomes due at 9 AM may not surface until the next nightly cycle. Since `review_at` is date-based (not time-based), this is acceptable — the nightly cycle runs before the user’s morning commit, so decisions due today will be present when Today Mode loads. This tradeoff is explicitly chosen over adding a same-day refresh path, which would add complexity without meaningful user benefit for date-granularity signals.

### 9.3 detection_cycles Table

▶ **[Addendum NEW]** Observability table for detection loop runs. Enables debugging and explainability audits.

|Column                |Type             |Description                                |
|----------------------|-----------------|-------------------------------------------|
|`id`                  |UUID (PK)        |`detection_cycle_id` referenced by alerts  |
|`user_id`             |UUID (FK → users)|Owner                                      |
|`started_at`          |TIMESTAMPTZ      |Cycle start time                           |
|`completed_at`        |TIMESTAMPTZ NULL |Cycle completion time                      |
|`status`              |ENUM             |`running`, `completed`, `failed`           |
|`domains_processed`   |TEXT[]           |Which domain producers ran                 |
|`candidates_produced` |INTEGER          |Total AlertCandidates produced             |
|`alerts_materialized` |INTEGER          |New alerts created                         |
|`alerts_updated`      |INTEGER          |Existing alerts updated (changed condition)|
|`alerts_auto_resolved`|INTEGER          |Alerts auto-resolved this cycle            |
|`alerts_unsnoozed`    |INTEGER          |Snoozed alerts reactivated or auto-resolved|
|`error_detail`        |TEXT NULL        |Error message if failed                    |

**Layer classification:** ▶ **[Rev2 CHANGE]** `detection_cycles` is Temporal by shape (time-bound, append-heavy, not semantically linked) and operational by retention class (30-day retention, purgeable). It is not Derived — it records what happened during a detection run, not a recomputable interpretation. The table is classified as Temporal with an operational retention policy, distinct from the indefinite retention of standard Temporal tables like `task_execution_events`.

-----

## 10. Entity Deletion & Orphan Handling

▶ **[Rev2 NEW]** This section defines how alert rows behave when referenced Core entities are hard-deleted. The v6 architecture (B-02) specifies that hard deletion cascades edges, flags Temporal records, and purges Derived caches. Alerts require an analogous rule.

### 10.1 Deletion Cascade for Alerts

When a Core node referenced in `entity_refs.primary` is hard-deleted:

- **Active alerts:** Transition to `status = auto_resolved`, `resolved_at = now()`. The condition that triggered the alert no longer exists. The alert row is retained as behavioral history (the user/system acted on it at some point, or the entity was deleted while the alert was active).
- **Snoozed alerts:** Same treatment — transition to `auto_resolved`. The snooze is irrelevant if the entity is gone.
- **Behavioral-history rows** (dismissed, resolved, auto_resolved): No change. They are already terminal and serve as audit records. The `entity_refs` will contain a reference to a deleted node, which is expected — the same pattern as Temporal records receiving `node_deleted = true`.

When a Core node referenced only in `entity_refs.related` (not `primary`) is deleted:

- No status change. The alert’s primary subject still exists. The `related` entry becomes a dead reference, which is acceptable — the UI should handle missing related entities gracefully (show “[deleted]” or omit).

### 10.2 Detection Loop Enforcement

The orphan check (step 6 in § 9.1) runs every detection cycle. It queries for active/snoozed alerts whose `entity_refs.primary.id` no longer exists in the `nodes` table and auto-resolves them. This is a safety net — in most cases, the deletion cascade should have already handled the transition, but the detection loop catches any race conditions or missed cascades.

### 10.3 Invariant

See A-10 in § 14.

-----

## 11. Migration & Supersession

### 11.1 finance_alerts → alerts

1. Rename `finance_alerts` to `alerts`.
1. Add columns: `domain`, `original_severity`, `source_hash`, `detection_cycle_id`, `producer_class`, `today_mode_channel`, `routing_snapshot`.
1. Backfill `domain = 'finance'` for all existing rows.
1. Backfill `original_severity = severity` for all existing rows.
1. Backfill `producer_class = 'entity_state'` for all existing rows (correct for all current finance alert types; `impulse_cluster` and other aggregate types are Phase 3+ and won’t exist yet).
1. Migrate `alert_type` ENUM values to TEXT with domain prefix (e.g., `low_cash_runway` → `finance.low_cash_runway`).
1. Migrate `entity_refs` to standardized shape: `{ primary: { type, id }, related: [...] }`.
1. Drop `alert_type` ENUM constraint; add TEXT CHECK constraint.

Zero downtime: Run as a single migration transaction. Finance detection loop updated to emit domain-prefixed types in the same release.

### 11.2 snooze_records Absorption

For each active `snooze_record`, create or update an alert in the `alerts` table with `status = snoozed` and the corresponding `snoozed_until`.

**Alert type inference is best-effort only.** ▶ **[Rev2 CHANGE]** The original `snooze_records` table does not preserve signal identity — it records that a node was snoozed, not which specific alert condition triggered the snooze. Inferring alert type from node type is lossy: a task node could map to `tasks.stale_todo`, `tasks.stale_in_progress`, or a future alert type depending on its state at snooze time.

**Migration rules:**

- Infer alert type using the node’s current state as a heuristic: snoozed task with `status = todo` → `tasks.stale_todo`; snoozed task with `status = in_progress` → `tasks.stale_in_progress`; snoozed goal → `goals.stale_goal`; snoozed source → `sources.unprocessed_raw`.
- If the node type/state does not map cleanly to a single alert type, migrate as `legacy.snoozed` — a special migration-only alert type that the system treats as a generic snooze. These rows expire normally via `snoozed_until` and are not re-emitted by any producer. They will either unsnooze into a real alert (if the detection loop produces a matching candidate) or auto-resolve.
- After migration verification: drop `snooze_records` table.
- Update Cleanup System code to read snooze state from `alerts` table instead of `snooze_records`.

▶ **[Addendum CHANGE]** `snooze_records` (v6 Temporal § 3.5) is removed from the Temporal layer. Snooze is now a lifecycle state within the Behavioral alerts system.

### 11.3 Decision Resurfacing Absorption

Decision resurfacing (v6 § 5.7) becomes a detection producer in the decisions domain. The standalone query-at-load-time pattern is replaced by nightly detection that materializes `decisions.review_due` and `decisions.outcome_missing_*` alerts.

Routing: `review_due` at medium severity (Cleanup queue). `outcome_missing` escalates from `low → medium → high` based on duration.

This is a behavioral change: decision resurfacing is no longer query-at-load-time. It is pre-materialized by the detection loop. See § 9.2 for the latency tradeoff rationale.

### 11.4 Cleanup System Integration

The Cleanup System’s review queues (v6 § 5.6) become consumers of medium-severity alerts:

|Cleanup Queue (v6)  |Alert Source (Addendum)                             |Change                                                    |
|--------------------|----------------------------------------------------|----------------------------------------------------------|
|Stale Tasks         |`tasks.stale_todo`, `tasks.stale_in_progress`       |Was: ephemeral Derived flag. Now: lifecycle-managed alert.|
|Inactive Goals      |`goals.stale_goal`                                  |Was: ephemeral flag. Now: alert with auto-resolution.     |
|Unprocessed Sources |`sources.unprocessed_raw`, `sources.capture_backlog`|Was: query-time count. Now: alert with snooze support.    |
|Low-signal KB       |`kb.stale_entry`, `kb.duplicate_detected`           |Was: lint job output. Now: alert with dismiss learning.   |
|Finance Review Queue|`finance.*` (medium severity)                       |Unchanged. Already alert-driven in Rev3.                  |

### 11.5 Finance Roadmap Supersession

▶ **[Rev2 NEW]** This addendum explicitly revises the finance module roadmap and invalidates the earlier standalone `finance_alerts` implementation path. The finance Rev3 document places the finance Alerts Engine in Finance Phase 2. This addendum requires that the unified `alerts` table exist before Finance Phase 2 ships, which means MVP Phase 4 creates the table and Finance Phase 2 consumes it.

**What this supersedes:** Finance Rev3’s plan to build `finance_alerts` as a standalone table in Finance Phase 2 is replaced. Finance Phase 2 now targets the unified `alerts` table created in MVP Phase 4. No standalone `finance_alerts` table is ever built — the migration described in § 11.1 applies only if an earlier phase has already created `finance_alerts`, which under the revised sequencing it will not have.

-----

## 12. Settings Integration

### 12.1 Typed Table: alert_settings

▶ **[Addendum NEW]** New typed settings table for cross-domain alert behavior. Follows settings addendum patterns.

|Column                           |Type                 |Default|Description                                                                               |
|---------------------------------|---------------------|-------|------------------------------------------------------------------------------------------|
|`user_id`                        |UUID (PK, FK → users)|—      |Owner                                                                                     |
|`global_alert_enabled`           |BOOLEAN              |`true` |Master kill switch for all alert detection.                                               |
|`suppression_threshold_downgrade`|NUMERIC(3,2)         |0.70   |`suppression_score` above this triggers severity downgrade. `CHECK (BETWEEN 0.5 AND 1.0)` |
|`suppression_threshold_mute`     |NUMERIC(3,2)         |0.90   |`suppression_score` above this mutes the alert type. `CHECK (BETWEEN 0.7 AND 1.0)`        |
|`cooldown_trigger_count`         |SMALLINT             |3      |Dismissals within `cooldown_window_days` to trigger cooldown. `CHECK (BETWEEN 1 AND 10)`  |
|`cooldown_window_days`           |SMALLINT             |7      |Window for counting rapid dismissals. `CHECK (BETWEEN 1 AND 30)`                          |
|`cooldown_duration_days`         |SMALLINT             |30     |Duration of automatic cooldown. `CHECK (BETWEEN 7 AND 90)`                                |
|`max_high_severity_per_day`      |SMALLINT             |2      |Engine-level cap on high-severity alerts surfaced to Today Mode. `CHECK (BETWEEN 1 AND 5)`|
|`max_high_per_domain`            |SMALLINT             |1      |Per-domain cap for high-severity in Today Mode. `CHECK (BETWEEN 1 AND 3)`                 |
|`created_at`                     |TIMESTAMPTZ          |—      |Row creation                                                                              |
|`updated_at`                     |TIMESTAMPTZ          |—      |Last modification                                                                         |

**Ordering invariant:** `suppression_threshold_downgrade` < `suppression_threshold_mute`. You must suppress harder to mute than to downgrade.

### 12.2 Dynamic EAV Extensions

Per-alert-type toggles and domain-specific overrides use the dynamic EAV table (`user_settings_dynamic`) under namespace `alerts`.

**Example keys:**

- `alerts.finance.low_cash_runway.enabled` → boolean, default `true`
- `alerts.tasks.stale_todo.enabled` → boolean, default `true`
- `alerts.goals.drift_detected.severity_override` → enum (`high`/`medium`/`low`), default `null`

These follow the settings addendum registry pattern: each key is registered in code with type, default, validation, and UI metadata. No migration required to add new alert type toggles.

**Severity override precedence:** When a user sets `severity_override` via EAV, this is step 2 in the severity precedence chain (§ 7.1). It overrides producer severity but is still subject to suppression downgrade. This is the only mechanism that can set severity higher than the producer recommendation, and it requires explicit user action.

### 12.3 Relationship to finance_settings

`finance_settings` retains domain-specific thresholds (`anomaly_threshold`, `low_cash_runway_days`, `stale_pending_days`, etc.). These drive the Derived computation that produces `AlertCandidates`. The `alert_settings` table controls what happens after candidates are produced (suppression, routing, caps).

**Principle:** Domain settings control signal detection. Alert settings control signal lifecycle.

-----

## 13. v6 Architecture Impact

### 13.1 Temporal Layer Changes

- `snooze_records` removed from Section 3.5 and the Temporal table registry. Snooze is now a lifecycle state in the Behavioral alerts table.
- `detection_cycles` added as a new Temporal table (operational telemetry, 30-day retention). Meets Temporal admission criteria: time-bound, append-heavy, not semantically linked. Retention is operational (30 days), not the standard Temporal indefinite retention — this is a retention policy exception, not a layer classification change.

### 13.2 Derived Layer Changes

- Stale content flags (Section 4.6) remain Derived outputs. They are now consumed by domain detection producers instead of being queried directly by the Cleanup System.
- Cleanup queue prioritization changes source: was “stale detection + `snooze_records`”, now “`alerts` WHERE `severity = medium` AND `status = active`.”

### 13.3 Behavioral Layer Changes

- Cleanup System (Section 5.6) becomes a pure consumer of the `alerts` table for review queue population. Snooze/dismiss actions now update alert status instead of creating `snooze_records`.
- Decision Resurfacing (Section 5.7) is absorbed into the decisions domain producer. The standalone section can reference this addendum.
- Today Mode (Section 5.1): High-severity alerts earn slots through existing P1/P4 channels via the `today_mode_channel` mechanism. No new Today Mode section is added. The routing engine determines placement; Today Mode rendering maps alerts into the appropriate existing section.

### 13.4 Visibility Precedence Update

v6 § 1.6 defines: Archived > Snoozed > Stale. This remains correct but the mechanism changes:

- **Archived:** Core (`archived_at IS NOT NULL`). Unchanged.
- **Snoozed:** Was: `snooze_records` (Temporal). Now: `alerts.status = 'snoozed'` (Behavioral).
- **Stale:** Was: Derived flag queried at render time. Now: `alerts.status = 'active'` with relevant stale `alert_type`.

### 13.5 Deletion Cascade Update

v6 § 1.7 (B-02) defines hard-delete cascade behavior. This addendum extends it:

- Active/snoozed alerts referencing a deleted Core node (via `entity_refs.primary`) are auto-resolved. See § 10.

### 13.6 Design Decisions Log Entries

**10.43 Alert Materialization Contract**  
The core abstraction is a Derived → Behavioral materialization contract, not a shared table. Domain producers emit `AlertCandidate` objects conforming to a formal schema. The Behavioral layer materializes, deduplicates, and manages lifecycle. The table is an implementation detail of the contract.

**10.44 TEXT Over ENUM for alert_type**  
`alert_type` uses TEXT with domain-prefixed naming (`domain.signal_name`) instead of ENUM. Avoids migration overhead for new alert types. Validated by code-side registry and database CHECK constraint on format. Consistent with the registry-driven architecture direction.

**10.45 snooze_records Absorption**  
Snooze is a lifecycle state, not an independent Temporal record. Moving it into the alerts table provides auto-resolution (the signal may clear while snoozed), dismiss-pattern learning, and a single mechanism for all deferred-attention patterns across all domains.

**10.46 Decision Resurfacing as Alert Producer**  
Decision resurfacing transitions from a query-at-load-time pattern to a materialized alert pattern. This gives decisions the same lifecycle management (snooze, dismiss, auto-resolve) as all other system-detected signals. The user experience is identical; the mechanism is unified. Deliberate latency tradeoff: nightly materialization for date-based signals is acceptable (see § 9.2).

**10.47 Engine-Level Attention Enforcement**  
Attention budget enforcement (U-01, U-02) is pushed into the routing engine, not just the UI rendering layer. The engine applies domain quotas and global caps before emitting signals to surfaces. This prevents alert fatigue at the source rather than masking it at the display layer.

**10.48 Suppression as Behavioral Adaptation**  
Dismiss-pattern learning is generalized from finance to all domains via the `alert_preferences` table. Suppression scores decay with a 90-day half-life, ensuring the system adapts to changed user behavior. Explicit overrides (“Always show” / “Never show”) take precedence over computed scores. v1 suppression is type-level only — intentionally coarse, with scoped suppression deferred.

**10.49 Severity is Monotonic Downward** ▶ [Rev2 NEW]  
After producer recommendation, severity can only be preserved or downgraded — never upgraded by suppression or routing. User override (EAV) is the sole exception and requires explicit user action. This ensures severity always means “how serious is this condition” and never drifts into “how much attention capacity exists today.”

**10.50 Alert Row Duality** ▶ [Rev2 NEW]  
The alerts table contains projection-state rows (active, snoozed) and behavioral-history rows (dismissed, resolved, auto_resolved). Projection rows are regenerable from the detection loop; history rows are permanent user/system interaction records. Both share one table and one lifecycle state machine. The distinction is semantic, not physical.

**10.51 Full-Snapshot Producer Default** ▶ [Rev2 NEW]  
Producers must emit the full current set of active candidates by default. Delta mode is an exception requiring explicit registration and a reconciliation path. This keeps auto-resolution simple and the absence-of-signal rule unambiguous.

**10.52 Today Mode Channel Routing** ▶ [Rev2 NEW]  
High-severity alerts route through existing Today Mode sections (P1/P4/review), not a dedicated alert slot. Producers declare a preferred `today_mode_channel`. This preserves Today Mode as a behavior engine rather than a generic notification surface.

-----

## 14. Invariants

▶ **[Addendum NEW]** New invariants extending the v6 Invariants Appendix (Section 13).

**A-01: Alert Materialization Contract**  
Every domain that produces alerts must emit `AlertCandidate` objects conforming to the schema in Section 3.1. The Behavioral layer materializes candidates; producers never write directly to the `alerts` table.

**A-02: Alerts Are Projections (Active State)**  
Projection-state rows (`active`, `snoozed`) in the `alerts` table are Behavioral projections of Derived signals. Deleting all projection-state rows and re-running detection must reproduce an equivalent set of active alerts. Behavioral-history rows (`dismissed`, `resolved`, `auto_resolved`) are interaction records and are not subject to this recomputation guarantee.

**A-03: Domain Prefix Consistency**  
`alerts.domain` must equal the prefix of `alerts.alert_type`. Enforced by CHECK constraint: `domain = split_part(alert_type, '.', 1)`.

**A-04: Active Dedup Uniqueness**  
At most one active alert per `(user_id, dedup_key)`. Enforced by partial unique index `WHERE status = 'active'`.

**A-05: Suppression Ordering**  
`alert_settings.suppression_threshold_downgrade` < `suppression_threshold_mute`. Downgrade must occur before muting.

**A-06: Engine-Level Attention Caps**  
The routing engine enforces `max_high_severity_per_day` and `max_high_per_domain` before emitting to Today Mode. UI-level suppression is a secondary safety net, not the primary enforcement mechanism.

**A-07: Detection Cycle Traceability**  
Every materialized or updated alert must reference a valid `detection_cycle_id`. Orphaned alerts (no `detection_cycle_id`) are invalid and must be auto-resolved on next cycle.

**A-08: source_hash Change Detection**  
Same `dedup_key` with changed `source_hash` = condition changed (update `explanation`, `source_hash`, `last_seen_at`). Same `dedup_key` with same `source_hash` = condition persists (touch `last_seen_at` only). This distinction enables UI to show “updated” badges on changed alerts.

**A-09: Cooldown Visibility**  
Active cooldowns must be visible in the alert settings UI with remaining duration and override option. Users must never be unaware that alert types are being suppressed.

**A-10: Entity Deletion Cascades to Alerts** ▶ [Rev2 NEW]  
When a Core node is hard-deleted, active and snoozed alerts referencing it via `entity_refs.primary` must transition to `auto_resolved`. Behavioral-history rows are not affected. The detection loop orphan check (§ 9.1, step 6) is a safety net for race conditions.

**A-11: Dedup Key Declaration Required** ▶ [Rev2 NEW]  
Every producer must declare canonical dedup dimensions for each alert type it emits. A producer that emits an `alert_type` without a registered dedup dimension declaration is rejected at startup.

**A-12: Severity Monotonic Downward** ▶ [Rev2 NEW]  
After producer recommendation (`original_severity`), the severity precedence chain (§ 7.1) may only preserve or downgrade severity. Suppression and routing never upgrade severity. User override via EAV is the sole exception.

**A-13: Cooldown Severity Awareness** ▶ [Rev2 NEW]  
Automatic cooldown applies only to low-severity alert types by default. Medium-severity types require producer opt-in. High-severity types are never eligible for automatic cooldown.

**A-14: Producer Snapshot Contract** ▶ [Rev2 NEW]  
Full-snapshot producers must emit the complete current set of active candidates for their scope on each detection cycle. Delta-mode producers require explicit registration and a reconciliation path enabling stale alert auto-resolution.

-----

## 15. Roadmap Placement

### 15.1 Implementation Sequence

|Phase                             |Scope                                                                                                                                                                                              |Dependencies                                                    |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
|**MVP Phase 4** (Goals + Derived) |`alerts` table schema. Tasks + Goals domain producers. Basic detection loop (nightly). Cleanup System integration. `snooze_records` migration. Producer registry with dedup dimension declarations.|Phase 3 (Core entities). `task_settings`, `today_mode_settings`.|
|**MVP Phase 5** (Behavioral Loops)|KB + Sources domain producers. Decisions domain producer. Detection cycle observability. `alert_preferences` (basic). `alert_settings` typed table. Routing snapshot.                              |Phase 4 (`alerts` table). `kb_settings`.                        |
|**Finance Phase 2** (Intelligence)|Finance domain producers targeting unified `alerts` table. No standalone `finance_alerts` table. Finance-specific routing preserved via `today_mode_channel`.                                      |`alerts` table from MVP Phase 4.                                |
|**Finance Phase 3** (Behavioral)  |Pattern-based finance alerts (`subscription_detected`, `spend_creep`, etc.). Aggregate producer classification. Full suppression engine.                                                           |Finance Phase 2. Recurring patterns.                            |
|**Post-MVP Phase B**              |Severity-aware cooldown mechanism. Full `suppression_score` computation. Per-alert-type EAV toggles in settings UI.                                                                                |Phase 5 `alert_preferences`.                                    |

### 15.2 Deferred (Not Designed)

- Push notification delivery channel (Notifications section in settings IA).
- Email digest of accumulated alerts.
- Alert-to-task conversion (“Convert this alert into a task” action).
- Cross-domain correlation alerts (e.g., “Spending rises when mood drops” — requires Phase C analytics).
- Scoped suppression by entity, account, category, or domain segment.

-----

## 16. Revision History

|Revision|Date      |Summary of Changes                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
|--------|----------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|Rev1    |April 2026|Initial unified alerts system design. Alert Materialization Contract. Unified alerts table replacing `finance_alerts` + `snooze_records`. Six domain taxonomies. Three-tier routing generalized. Engine-level attention enforcement. Suppression memory. Detection loop architecture with cycle observability. `alert_settings` typed table. 9 invariants (A-01 through A-09). 6 design decisions (10.43 through 10.48). Migration path for `finance_alerts`, `snooze_records`, and decision resurfacing.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
|Rev2    |April 2026|Producer contract (§ 4): full-snapshot default, delta escape hatch, dedup key construction rules, dependency constraints, idempotency requirement. Producer classification into entity-state vs. aggregate with lifecycle implications. Alert row duality (§ 2.4): projection-state vs. behavioral-history rows. Severity precedence chain (§ 7.1): monotonic downward, explicit four-step resolution. Today Mode routing via existing channels (§ 7.2): no unified alert slot, producers declare `today_mode_channel`. Routing state explainability via `routing_snapshot` (§ 7.3). Severity-aware cooldown (§ 8.4): high-severity never auto-cooldown, medium requires producer opt-in. Suppression scope limitation acknowledged (§ 8.3). Entity deletion orphan handling (§ 10). Decision resurfacing latency tradeoff called out (§ 9.2). Snooze migration as best-effort with `legacy.snoozed` fallback (§ 11.2). Finance roadmap supersession made explicit (§ 11.5). `entity_refs.type` registry-governed (§ 3.2). `detection_cycles` layer classification clarified (§ 9.3). 5 new invariants (A-10 through A-14). 4 new design decisions (10.49 through 10.52).|

-----

*— End of Document —*