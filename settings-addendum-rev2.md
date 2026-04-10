**PERSONAL OS**

Settings System Addendum

Architecture v6 Addendum | April 2026

*Unified settings architecture: typed tables for system logic, dynamic EAV for preferences, code-side registry for validation and UI generation.*

**Core:** Typed domain tables (system, AI, Today Mode, finance, tasks, KB) + dynamic EAV table

**Registry:** Code-side SettingDefinition declarations powering validation, defaults, and UI

**UX:** Settings as a control surface with impact-level progressive disclosure and inline explainability

# 1. Architecture Overview

Settings are a Core layer concern — durable, user-owned configuration that governs system behavior. They do not participate in the graph (they fail the “is this one of my things” test), are not Temporal (not event-based), and are not Derived (not recomputable). They sit alongside templates as Core configuration tables.

## 1.1 Two-Tier Storage Model

The settings system uses a hybrid storage model: typed tables for system-critical settings and a dynamic EAV table for preferences and fast-evolving configuration.

### Tier 1 — Typed Tables (Domain-Aligned)

One table per behavioral/system domain. Explicit Postgres columns with types, constraints, and defaults. Migration required for schema changes.

|**Table**          |**Domain**         |**Governs**                                                     |
|-------------------|-------------------|----------------------------------------------------------------|
|system_settings    |General            |Timezone, currency, week boundaries                             |
|ai_settings        |AI & Intelligence  |Suggestion modes, confidence thresholds, retrieval bias         |
|today_mode_settings|Today Mode         |Attention budget caps, suppression, behavioral toggles          |
|finance_settings   |Finance            |Alert thresholds, anomaly detection, forecasting, reconciliation|
|task_settings      |Tasks & Habits     |Stale detection, planning horizon, streaks                      |
|kb_settings        |Knowledge & Sources|Pipeline modes, dedup thresholds, staleness windows             |

### Tier 2 — Dynamic EAV Table

One row per setting in user_settings_dynamic. Used for preferences, feature flags, experiments, UX configuration, and fast-evolving module settings. No migration required for new settings.

## 1.2 Admission Rule

***Typed if the setting participates in system logic, computation, or invariants. Dynamic if it only affects user preference or presentation.***

A setting is Typed if ANY of the following is true:

• **Affects Behavioral decisions:** routing, ranking, alert triggering, workflow logic.

• **Used in Derived computations:** thresholds, scoring, anomaly detection, forecasting.

• **Enforces invariants or safety:** caps (Today Mode limits), confidence thresholds, validation boundaries.

• **Requires strict validation:** bounded ranges, inter-field constraints, business logic dependencies.

Everything else → Dynamic.

## 1.3 Settings Registry (Code-Side Source of Truth)

A typed Python definition that declares every valid setting across both tiers. Not a database table. The registry is the schema contract; the database is storage.

Registry responsibilities:

• **Validation:** Type, range, enum membership, and cross-field constraints on every write.

• **Defaults:** When a user has no override, the registry supplies the default. No need to seed rows for every user.

• **UI generation:** The frontend reads the registry (via API) to render settings sections, labels, descriptions, impact badges, and “what it affects” tooltips.

• **Storage routing:** The registry knows whether a setting is typed or dynamic, so the API reads/writes the correct location transparently.

• **Progressive disclosure:** impact_level drives the basic/advanced split in the UI.

### SettingDefinition Schema

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional

class ValueType(Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    ENUM = "enum"

class StorageType(Enum):
    TYPED = "typed"
    DYNAMIC = "dynamic"

class ImpactLevel(Enum):
    SAFE = "safe"
    BEHAVIORAL = "behavioral"
    CRITICAL = "critical"

class Mutability(Enum):
    USER = "user"
    SYSTEM = "system"
    READ_ONLY = "read_only"

@dataclass
class TypedStorage:
    table: str
    column: str

@dataclass
class ValidationRule:
    min: float | None = None
    max: float | None = None
    regex: str | None = None
    custom: Callable[[Any], bool] | None = None

@dataclass
class SettingDefinition:
    namespace: str
    key: str

    storage: StorageType
    typed: Optional[TypedStorage]

    value_type: ValueType
    default: Any

    enum_values: Optional[List[Any]] = None
    validation: Optional[ValidationRule] = None
    cross_validation: Optional[List[Callable]] = None

    mutability: Mutability = Mutability.USER
    feature_flag: Optional[str] = None

    affects: List[str]
    description: str

    section: str
    subsection: Optional[str] = None

    impact_level: ImpactLevel = ImpactLevel.SAFE
    depends_on: Optional[List[str]] = None
```

|**Field**       |**Type**             |**Description**                              |
|----------------|---------------------|---------------------------------------------|
|namespace       |str                  |Grouping key: ai, finance, ui, etc.          |
|key             |str                  |Setting identifier within namespace          |
|storage         |StorageType          |typed or dynamic                             |
|typed           |TypedStorage | None  |Table and column if typed, None if dynamic   |
|value_type      |ValueType            |boolean, integer, float, string, enum        |
|default         |Any                  |Default value                                |
|enum_values     |list | None          |Allowed values for enum types                |
|validation      |ValidationRule | None|min, max, regex, custom callable             |
|cross_validation|list[Callable] | None|Cross-field/cross-table validators           |
|mutability      |Mutability           |user, system, or read_only                   |
|feature_flag    |str | None           |Ties visibility to an experiment flag        |
|affects         |list[str]            |Surfaces affected (for UI explainability)    |
|description     |str                  |Human-readable tooltip text                  |
|section         |str                  |Settings IA section name                     |
|subsection      |str | None           |Subsection within section                    |
|impact_level    |ImpactLevel          |safe, behavioral, or critical                |
|depends_on      |list[str] | None     |Settings this depends on (for conditional UI)|

# 2. Typed Table Schemas

*One table per domain. One row per user. All tables follow the same pattern: user_id as PK + FK, explicit typed columns with CHECK constraints, version for migration tracking, created_at/updated_at for audit.*

## 2.1 system_settings

Covers global identity and system-wide configuration. These settings affect cross-module behavior: Temporal joins, analytics window computation, and Derived calculations.

|**Column**      |**Type**             |**Default**|**Constraints**        |**Description**                                                                                              |
|----------------|---------------------|-----------|-----------------------|-------------------------------------------------------------------------------------------------------------|
|user_id         |UUID (PK, FK → users)|—          |—                      |Owner                                                                                                        |
|timezone        |TEXT                 |UTC        |NOT NULL               |IANA timezone. Affects Temporal joins, analytics windows, review scheduling, Derived computations.           |
|default_currency|TEXT                 |USD        |NOT NULL               |ISO 4217. Base currency for finance normalization, net worth computation, exchange rate conversion.          |
|week_starts_on  |SMALLINT             |1          |CHECK (BETWEEN 0 AND 1)|1=Monday, 0=Sunday. Governs weekly_snapshots boundaries, weekly rollup binning, analytics period computation.|
|version         |INTEGER              |1          |—                      |Schema version for migration and rollout logic                                                               |
|created_at      |TIMESTAMPTZ          |—          |NOT NULL               |Row creation                                                                                                 |
|updated_at      |TIMESTAMPTZ          |—          |NOT NULL               |Last modification                                                                                            |

## 2.2 ai_settings

Controls all AI/intelligence behavior across the system. Three automation modes use a consistent tri-state ENUM pattern: off (disabled), suggest_only (computed but requires user action), auto_with_review (acts automatically, user can dismiss).

|**Column**                         |**Type**             |**Default** |**Constraints**                      |**Description**                                                                                                                                                                            |
|-----------------------------------|---------------------|------------|-------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|user_id                            |UUID (PK, FK → users)|—           |—                                    |Owner                                                                                                                                                                                      |
|suggestion_mode                    |ENUM                 |suggest_only|(off, suggest_only, auto_with_review)|Controls link suggestions, inbox classification, AI briefing. Off = nothing produced. suggest_only = shown, no side effects. auto_with_review = creates pending_review edges and pre-fills.|
|linking_mode                       |ENUM                 |suggest_only|(off, suggest_only, auto_with_review)|Controls edge creation from AI. Off = no link suggestions. suggest_only = context layer only. auto_with_review = creates pending_review edges automatically.                               |
|classification_confidence_threshold|NUMERIC(3,2)         |0.85        |CHECK (BETWEEN 0 AND 1)              |Minimum confidence for auto-classifying inbox captures. Below → unclassified for manual triage.                                                                                            |
|link_confidence_threshold          |NUMERIC(3,2)         |0.70        |CHECK (BETWEEN 0 AND 1)              |Minimum confidence for surfacing link suggestions. Below → not shown.                                                                                                                      |
|max_suggestions_per_surface        |SMALLINT             |2           |CHECK (BETWEEN 0 AND 10)             |Cap on AI suggestions per surface. Must not exceed today_mode_settings.max_unsolicited_items (SET-01).                                                                                     |
|briefing_detail                    |ENUM                 |standard    |(minimal, standard, detailed)        |AI briefing generation. minimal = 3 bullets. standard = 5 bullets. detailed = 5 bullets + reasoning.                                                                                       |
|retrieval_recency_bias             |NUMERIC(3,2)         |0.30        |CHECK (BETWEEN 0 AND 1)              |Recency weight in signal score computation (v6 Section 4.1).                                                                                                                               |
|version                            |INTEGER              |1           |—                                    |Schema version                                                                                                                                                                             |
|created_at                         |TIMESTAMPTZ          |—           |NOT NULL                             |Row creation                                                                                                                                                                               |
|updated_at                         |TIMESTAMPTZ          |—           |NOT NULL                             |Last modification                                                                                                                                                                          |

**Note:** enrichment_mode lives in kb_settings (Section 2.6), not here. Enrichment is a knowledge pipeline concern. ai_settings controls intelligence behavior (suggestions, linking, briefings); kb_settings controls the content pipeline.

## 2.3 today_mode_settings

Controls the attention system — the most behavior-critical surface in Personal OS. These settings directly enforce invariants U-01 and U-02.

|**Column**                 |**Type**             |**Default**|**Constraints**         |**Description**                                                                                                                       |
|---------------------------|---------------------|-----------|------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
|user_id                    |UUID (PK, FK → users)|—          |—                       |Owner                                                                                                                                 |
|max_items                  |SMALLINT             |10         |CHECK (BETWEEN 5 AND 20)|Hard cap on total Today Mode items across all sections. Enforces U-02.                                                                |
|max_unsolicited_items      |SMALLINT             |2          |CHECK (BETWEEN 0 AND 5) |Cap on unsolicited intelligence items (goal nudges, resurfaced content, cleanup prompts, journal prompts). Enforces U-01.             |
|max_focus_tasks            |SMALLINT             |3          |CHECK (BETWEEN 1 AND 5) |Maximum user-committed focus tasks in morning commit. P0 section cap.                                                                 |
|max_due_today_tasks        |SMALLINT             |3          |CHECK (BETWEEN 0 AND 5) |Cap on due/overdue tasks shown. P1 section cap.                                                                                       |
|max_habits                 |SMALLINT             |2          |CHECK (BETWEEN 0 AND 5) |Cap on habit items. P2 section cap.                                                                                                   |
|max_learning_reviews       |SMALLINT             |3          |CHECK (BETWEEN 0 AND 5) |Cap on learning review items. P3 section cap.                                                                                         |
|suppression_start_threshold|SMALLINT             |8          |CHECK (BETWEEN 3 AND 20)|When total visible items reach this count, lower-priority sections (P5+) are suppressed. Drives suppression rules from v6 Section 5.1.|
|morning_commit_enabled     |BOOLEAN              |true       |—                       |Whether morning commit workflow activates on app open. When false, Today Mode shows system-ranked items without user commit step.     |
|evening_reflection_enabled |BOOLEAN              |true       |—                       |Whether evening reflection workflow triggers. When false, no plan-vs-actual prompt.                                                   |
|focus_session_tracking     |BOOLEAN              |true       |—                       |Whether focus sessions produce focus_sessions Temporal records. When false, focus mode is visual-only.                                |
|version                    |INTEGER              |1          |—                       |Schema version                                                                                                                        |
|created_at                 |TIMESTAMPTZ          |—          |NOT NULL                |Row creation                                                                                                                          |
|updated_at                 |TIMESTAMPTZ          |—          |NOT NULL                |Last modification                                                                                                                     |

**Invariant SET-02:** Per-section caps are ceilings, not allocations. Their sum may exceed max_items. The global max_items is the hard stop. Suppression rules apply in priority order (P0→P7) when the budget fills.

## 2.4 finance_settings

Controls financial behavior, alert routing, and Derived computation thresholds. The most invariant-dense settings table due to the Alerts Engine.

|**Column**                       |**Type**             |**Default**|**Constraints**                |**Description**                                                                                                                        |
|---------------------------------|---------------------|-----------|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
|user_id                          |UUID (PK, FK → users)|—          |—                              |Owner                                                                                                                                  |
|low_cash_runway_days             |SMALLINT             |—          |CHECK (BETWEEN 1 AND 60)       |Projected cash runway below this many days triggers low_cash_runway alert (high severity). Affects Alerts Engine routing to Today Mode.|
|large_transaction_multiplier     |NUMERIC(4,2)         |—          |CHECK (>= 1)                   |Transaction amount exceeding this × category median triggers large_transaction alert.                                                  |
|category_spike_multiplier        |NUMERIC(4,2)         |—          |CHECK (>= 1)                   |Current period category spend exceeding this × rolling 3-month average triggers category anomaly.                                      |
|unreconciled_divergence_threshold|NUMERIC(4,3)         |—          |CHECK (BETWEEN 0 AND 0.5)      |Computed vs reconciled balance divergence ratio triggering unreconciled_divergence alert.                                              |
|uncategorized_aging_days         |SMALLINT             |—          |CHECK (BETWEEN 1 AND 30)       |Uncategorized transactions older than this trigger uncategorized_aging alert.                                                          |
|stale_pending_days               |SMALLINT             |—          |CHECK (BETWEEN 1 AND 30)       |Pending transactions older than this trigger stale_pending alert.                                                                      |
|burn_rate_runway_months          |SMALLINT             |—          |CHECK (BETWEEN 1 AND 24)       |Burn rate forecast triggers Today Mode warning when liquid runway falls below this many months.                                        |
|reconciliation_reminder_days     |SMALLINT             |—          |CHECK (BETWEEN 1 AND 90)       |Days since last reconciled snapshot before reconciliation nudge.                                                                       |
|goal_off_track_mode              |TEXT                 |—          |CHECK (IN (off, notify, nudge))|Off = no alerts. notify = passive in finance module. nudge = routes to Today Mode via Alerts Engine.                                   |
|version                          |INTEGER              |1          |—                              |Schema version                                                                                                                         |
|created_at                       |TIMESTAMPTZ          |—          |NOT NULL                       |Row creation                                                                                                                           |
|updated_at                       |TIMESTAMPTZ          |—          |NOT NULL                       |Last modification                                                                                                                      |

## 2.5 task_settings

Controls task execution system, stale detection thresholds, and planning behavior. Includes inter-field ordering invariants.

|**Column**              |**Type**             |**Default**|**Constraints**                     |**Description**                                                                           |
|------------------------|---------------------|-----------|------------------------------------|------------------------------------------------------------------------------------------|
|user_id                 |UUID (PK, FK → users)|—          |—                                   |Owner                                                                                     |
|stale_todo_days         |SMALLINT             |14         |CHECK (BETWEEN 1 AND 90)            |Days untouched before a todo task is flagged stale. Feeds Derived stale content detection.|
|stale_in_progress_days  |SMALLINT             |7          |CHECK (BETWEEN 1 AND 60)            |Days untouched before an in_progress task is flagged stale.                               |
|stale_goal_days         |SMALLINT             |30         |CHECK (BETWEEN 1 AND 365)           |Days without progress before an active goal is flagged.                                   |
|default_priority        |TEXT                 |none       |CHECK (IN (none, low, medium, high))|Default priority assigned to new tasks. Affects Behavioral task creation.                 |
|planning_horizon_days   |SMALLINT             |7          |CHECK (BETWEEN 1 AND 30)            |How far ahead the system looks for upcoming due tasks in Today Mode and morning commit.   |
|streak_minimum_threshold|SMALLINT             |1          |CHECK (BETWEEN 1 AND 30)            |Minimum completed execution events per day to count toward consistency_streak.            |
|version                 |INTEGER              |1          |—                                   |Schema version                                                                            |
|created_at              |TIMESTAMPTZ          |—          |NOT NULL                            |Row creation                                                                              |
|updated_at              |TIMESTAMPTZ          |—          |NOT NULL                            |Last modification                                                                         |

**Ordering invariants (CHECK constraints):** stale_in_progress_days ≤ stale_todo_days ≤ stale_goal_days. An in-progress task should be flagged before an idle todo, which should be flagged before a stalled goal.

## 2.6 kb_settings

Controls the knowledge pipeline: source enrichment, deduplication, and content hygiene windows.

|**Column**             |**Type**             |**Default**|**Constraints**                     |**Description**                                                                                                               |
|-----------------------|---------------------|-----------|------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
|user_id                |UUID (PK, FK → users)|—          |—                                   |Owner                                                                                                                         |
|auto_enrichment_mode   |TEXT                 |—          |CHECK (IN (off, suggest_only, auto))|Controls LLM enrichment of source items. Off = manual only. suggest_only = runs but user reviews. auto = surfaces immediately.|
|dedup_similarity_cutoff|NUMERIC(3,2)         |—          |CHECK (BETWEEN 0.7 AND 1.0)         |Embedding similarity above this flags potential duplicate sources. Feeds Derived dedup detection.                             |
|stale_kb_days          |SMALLINT             |—          |CHECK (BETWEEN 7 AND 365)           |Days since last lint before an accepted KB entry is flagged stale.                                                            |
|stale_source_raw_days  |SMALLINT             |—          |CHECK (BETWEEN 1 AND 30)            |Days before an unprocessed (raw) source item is flagged.                                                                      |
|stale_inbox_days       |SMALLINT             |—          |CHECK (BETWEEN 1 AND 14)            |Days before an unclassified inbox item is flagged.                                                                            |
|version                |INTEGER              |1          |—                                   |Schema version                                                                                                                |
|created_at             |TIMESTAMPTZ          |—          |NOT NULL                            |Row creation                                                                                                                  |
|updated_at             |TIMESTAMPTZ          |—          |NOT NULL                            |Last modification                                                                                                             |

**Ordering invariants (CHECK constraints):** stale_inbox_days ≤ stale_source_raw_days ≤ stale_kb_days. Inbox items should be flagged fastest, raw sources next, accepted KB entries slowest.

# 3. Dynamic EAV Table

Handles all preferences, presentation config, feature flags, experiments, and fast-evolving module settings. No migration required to add new settings — only a registry entry in code.

## 3.1 user_settings_dynamic

|**Column**|**Type**         |**Constraints**                      |**Description**                                                                                               |
|----------|-----------------|-------------------------------------|--------------------------------------------------------------------------------------------------------------|
|id        |UUID (PK)        |—                                    |Primary key                                                                                                   |
|user_id   |UUID (FK → users)|NOT NULL                             |Owner                                                                                                         |
|namespace |TEXT             |NOT NULL, CHECK (~ ‘^[a-z_]+$’)      |Grouping key: ui, today_mode, finance, finance_alerts, ai, tasks, kb, notifications, integrations, experiments|
|key       |TEXT             |NOT NULL, CHECK (~ ‘^[a-z_]+$’)      |Setting identifier within namespace. Lowercase snake_case only.                                               |
|value_json|JSONB            |NOT NULL                             |Setting value (any JSON type)                                                                                 |
|source    |TEXT             |CHECK (IN (user, system, experiment))|Who set this value. user = user changed it. system = seeded or forced. experiment = set by feature flag.      |
|is_active |BOOLEAN          |DEFAULT true                         |Soft-disable without deleting. Deactivated settings are retained but not applied.                             |
|created_at|TIMESTAMPTZ      |NOT NULL                             |Row creation                                                                                                  |
|updated_at|TIMESTAMPTZ      |NOT NULL                             |Last modification                                                                                             |

*Constraint:* UNIQUE(user_id, namespace, key). One value per setting per user.

## 3.2 Example Dynamic Settings

|**Namespace** |**Key**                 |**Value**   |**Source**|**Description**                 |
|--------------|------------------------|------------|----------|--------------------------------|
|ui            |theme                   |“dark”      |user      |Color theme                     |
|ui            |date_format             |“YYYY-MM-DD”|system    |Date display format             |
|ui            |sidebar_collapsed       |false       |user      |Sidebar state                   |
|today_mode    |focus_style             |“minimal”   |user      |Focus view density              |
|finance_alerts|spend_creep_enabled     |true        |system    |Per-alert-type toggle           |
|finance_alerts|impulse_cluster_enabled |false       |user      |User disabled this alert type   |
|ai            |tone_preference         |“concise”   |user      |AI response style               |
|notifications |quiet_hours_start       |“22:00”     |user      |Notification suppression start  |
|experiments   |beta_semantic_clustering|true        |experiment|Feature flag for beta clustering|

Per-alert-type toggles are Dynamic because the alert type taxonomy grows over time (rule-based in Phase 2, pattern-based in Phase 3). A typed column per alert type would require a migration every time a new alert type ships.

# 4. Settings Information Architecture

The settings UI is organized as a sidebar-navigated page with sections mapped to system domains. Each section visually separates system behavior (advanced, with impact warnings) from preferences (safe, immediate effect).

## 4.1 Navigation Structure

```
Settings
├── General
├── AI & Intelligence
├── Today Mode
├── Notifications
├── Finance
├── Tasks & Habits
├── Knowledge & Sources
├── Privacy & Data
├── Integrations
└── Experiments
```

|**Section**        |**Storage Tier**                     |**Description**                                                        |
|-------------------|-------------------------------------|-----------------------------------------------------------------------|
|General            |Typed (system_settings)              |Identity + global preferences: timezone, currency, week boundaries     |
|AI & Intelligence  |Typed (ai_settings) + Dynamic        |Suggestion modes, thresholds, retrieval bias, tone, proactiveness      |
|Today Mode         |Typed (today_mode_settings) + Dynamic|Attention budget, section caps, behavioral toggles, focus style        |
|Notifications      |Dynamic                              |Push/email toggles, frequency, quiet hours                             |
|Finance            |Typed (finance_settings) + Dynamic   |Alert thresholds, anomaly detection, per-alert toggles, dashboard prefs|
|Tasks & Habits     |Typed (task_settings) + Dynamic      |Stale thresholds, planning horizon, streaks, recurrence defaults       |
|Knowledge & Sources|Typed (kb_settings) + Dynamic        |Pipeline modes, dedup, staleness windows, capture preferences          |
|Privacy & Data     |Typed (future) + Dynamic             |Export, deletion, AI logging, retention                                |
|Integrations       |Dynamic                              |API connections, sync settings                                         |
|Experiments        |Dynamic                              |Feature flags, beta features                                           |

## 4.2 UX Patterns

### Impact-Level Progressive Disclosure

Each section visually separates settings by impact level. Basic users see preferences only. Advanced controls are behind a disclosure toggle.

|**Impact Level**|**Visual Treatment**                   |**Behavior**                                                           |
|----------------|---------------------------------------|-----------------------------------------------------------------------|
|safe            |No special treatment                   |Immediate effect, no confirmation required                             |
|behavioral      |Labeled as “Advanced”                  |Affects system behavior. Brief explanation shown.                      |
|critical        |Warning indicator + confirmation dialog|Affects invariants or safety. Requires explicit confirmation on change.|

### Inline Explainability

Every non-trivial setting displays what it affects and where it shows up. This mirrors the DerivedExplanation philosophy (Invariant D-01). Example:

*Max Unsolicited Insights [2]*
*Controls how many AI suggestions appear in Today Mode and Context Layer.*
*Affects: Today View (P4–P7 sections), Context Layer (AI suggestions slot)*

### Default vs Customized

For typed settings, the UI compares the current value against the registry default and shows a “customized” indicator when they differ. A reset-to-default action is available on each customized setting. For dynamic settings, the source field (user/system/experiment) drives this display.

# 5. Settings Invariants

*These extend the v6 Invariants Appendix (Section 13) and the Finance Invariants (Section 9 of finance doc).*

**SET-01: AI Suggestions ≤ Unsolicited Cap**

ai_settings.max_suggestions_per_surface must not exceed today_mode_settings.max_unsolicited_items. Enforced at application layer on write. Cross-table CHECK not possible in Postgres without triggers.

**SET-02: Section Caps Are Ceilings**

Per-section caps in today_mode_settings are ceilings, not allocations. Their sum may exceed max_items. The global max_items is the hard stop. Suppression rules apply in priority order (P0→P7) when the budget fills.

**SET-03: Stale Detection Ordering (Tasks)**

task_settings: stale_in_progress_days ≤ stale_todo_days ≤ stale_goal_days. Enforced by CHECK constraints.

**SET-04: Stale Detection Ordering (KB)**

kb_settings: stale_inbox_days ≤ stale_source_raw_days ≤ stale_kb_days. Enforced by CHECK constraints.

**SET-05: Dynamic Key Format**

user_settings_dynamic.namespace and key must match ^[a-z_]+$ (lowercase snake_case only). Enforced by CHECK constraints.

**SET-06: Dynamic Uniqueness**

At most one row per (user_id, namespace, key) in user_settings_dynamic. Enforced by UNIQUE constraint.

**SET-07: Typed Tables Are Authoritative**

For any setting that exists in a typed table, the typed table is the source of truth. Dynamic settings must not shadow or override typed settings. The registry prevents this by routing reads/writes to the correct tier.

**SET-08: Registry Is Complete**

Every setting — typed or dynamic — must have a corresponding SettingDefinition in the registry. Settings without registry entries are invalid and must not be read or written by the application.

# 6. Design Decisions Log

*Extending Section 12 of the v6 architecture document and Section 10 of the finance module doc.*

**10.28 Hybrid Typed + EAV Storage Model**

Typed tables for system-critical settings, dynamic EAV for preferences. Avoids both premature rigidity (all-typed) and schema chaos (all-JSONB). Admission rule based on participation in system logic, not read frequency.

**10.29 Admission Rule: Logic, Not Frequency**

“Typed if the setting participates in system logic, computation, or invariants. Dynamic if it only affects user preference or presentation.” Read frequency is a performance concern, not an architectural one. Theme is read every request but is Dynamic; a confidence threshold is read rarely but is Typed.

**10.30 One Typed Table Per Domain**

Each behavioral/system domain gets its own typed table. This provides maximum type safety, domain-aligned constraints (including inter-field ordering invariants), and clear ownership boundaries. The alternative — consolidating into fewer tables — was rejected because it would mix unrelated constraints and make domain-specific migrations harder.

**10.31 Tri-State Automation Modes**

Binary toggles (enabled/disabled) replaced with tri-state ENUMs (off / suggest_only / auto_with_review) for AI automation controls. The middle state — suggest_only — is the natural default for a system that values user agency. Consistent pattern across suggestion_mode, linking_mode, and auto_enrichment_mode.

**10.32 No Source Tracking on Typed Tables**

Typed tables do not store per-field source metadata. Override detection works by comparing current values against registry defaults at read time. Dynamic settings store source per-row (user/system/experiment) because there is no schema to compare against.

**10.33 Enrichment Mode in kb_settings, Not ai_settings**

Enrichment is a knowledge pipeline concern, not a general AI concern. ai_settings controls intelligence behavior (suggestions, linking, briefings); kb_settings controls the content pipeline. Prevents two knobs controlling the same engine.

**10.34 Per-Alert-Type Toggles Are Dynamic**

The alert type taxonomy grows over time (rule-based in Phase 2, pattern-based in Phase 3). Per-alert-type enable/disable toggles live in user_settings_dynamic (namespace: finance_alerts) to avoid migrations on every new alert type.

**10.35 NUMERIC Over FLOAT for Thresholds**

All threshold and multiplier columns use NUMERIC, not FLOAT. Deterministic behavior, no float drift, safer comparisons in logic, and consistency with the finance module’s monetary precision.

**10.36 Inter-Field Ordering Invariants**

task_settings and kb_settings enforce ordering relationships between stale detection thresholds via CHECK constraints (e.g., stale_in_progress_days ≤ stale_todo_days ≤ stale_goal_days). These are textbook examples of why typed tables exist — EAV cannot enforce cross-field constraints at the DB level.

# 7. Roadmap Placement

## 7.1 MVP Phase 1 Additions

system_settings table. user_settings_dynamic table. Settings registry scaffold with General section definitions. Basic settings API (read/write both tiers). Settings created on user account setup with registry defaults.

## 7.2 MVP Phase 2 Additions

task_settings table (stale detection thresholds used by Derived layer from Phase 4). today_mode_settings table (attention budget caps used by Today View).

## 7.3 MVP Phase 3 Additions

kb_settings table (pipeline modes, dedup threshold, staleness windows).

## 7.4 MVP Phase 5 Additions

ai_settings table (suggestion modes, confidence thresholds, retrieval bias — needed when AI modes ship).

## 7.5 Finance Phase 1 Additions

finance_settings table (alert thresholds, anomaly detection, reconciliation).

## 7.6 Post-MVP Additions

Privacy & data settings (typed table, designed when export/retention systems are closer to implementation). Notifications section (dynamic). Integrations section (dynamic). Experiments section (dynamic). Settings UI with full IA, progressive disclosure, and inline explainability.

*— End of Document —*