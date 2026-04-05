# Personal OS — Implementation Plan

## Coverage Verification

Before diving into phases, here is the complete inventory of everything in the v6 architecture doc, mapped to implementation phases. **Nothing is omitted.**

### Core Tables (Section 2)

- [P1] users
- [P1] nodes (with layer-classified fields: embedding=CACHED DERIVED, last_accessed_at=BEHAVIORAL TRACKING)
- [P1] edges (with relation_type enum, origin, state, weight, confidence, metadata)
- [P1] Edge type-pair constraint trigger (G-01)
- [P2] task_nodes (status enum, priority, due_date, recurrence, is_recurring cached flag)
- [P2] journal_nodes (mood ENUM: great/good/neutral/low/bad, word_count)
- [P3] kb_nodes (compile_status, pipeline_stage, compile_version)
- [P3] source_item_nodes (source_type, processing_status, triage_status, permanence, checksum)
- [P3] source_fragments (fragment_type, position, embedding)
- [P3] memory_nodes (memory_type enum, review_at)
- [P1] inbox_items (status lifecycle: pending/promoted/dismissed/merged/archived)
- [P8] project_nodes (future — active/completed/archived)
- [P2] templates (system config)

### Temporal Tables (Section 3)

- [P7] daily_plans
- [P8] weekly_snapshots
- [P8] monthly_snapshots
- [P7] focus_sessions
- [P6] snooze_records
- [P9] ai_interaction_logs
- [P2] task_execution_events

### Derived Computations (Section 4)

- [P5] Signal score (5-factor composite)
- [P5] Progress intelligence (progress, momentum, consistency_streak, drift_score)
- [P9] AI enrichments / node_enrichments table
- [P5] Retrieval modes (factual_qa, execution_qa, daily_briefing, reflection, improvement, link_suggestion)
- [P5] Memory retrieval context layer (2-stage: explicit links → suggested)
- [P6] Stale content detection (per-entity thresholds)
- [PC] Analytics architecture (3-tier output classification, 2-tier computation model)
- [PC] Analytics rollup tables (daily + weekly)
- [P9] Node enrichments table (versioned, superseded_at)
- [PC] Semantic clustering
- [PC] Smart resurfacing
- [P6] DerivedExplanation schema
- [P6] Cleanup queue prioritization

### Behavioral Flows (Section 5)

- [P4] Today View (primary entry point, 4-stage cycle)
- [P7] Morning commit
- [P7] Evening reflection
- [P7] Focus mode
- [P8] Weekly review (hybrid summary + guided workflow)
- [P8] Monthly review
- [P1] Capture workflow (Cmd+K search + capture)
- [P3] Source triage / promotion
- [P6] Cleanup system (batch actions, review queues, snooze)
- [P9] AI: Ask mode
- [P9] AI: Plan mode
- [P9] AI: Reflect mode
- [P9] AI: Improve mode
- [P9] Link suggestion (origin=llm, state=pending_review)
- [P9] KB lint pipeline
- [P9] Source auto-enrichment
- [P9] Inbox auto-classification
- [PB] Decision resurfacing

### Frontend (Section 9)

- [P1] Layout: Rail (48px) + List Pane (240px, resizable) + Detail Pane
- [P1] Design tokens (all colors, radius)
- [P1] Typography (IBM Plex Sans + Mono)
- [P5] Context layer (priority order, caps, suppression rules)
- [P4] Today View (full-width behavioral surface)
- [P4] Today Mode ranking policy + suppression rules

### Policies & Rules

- [P1] 7 layer interaction rules
- [P1] Visibility precedence (archived > snoozed > stale)
- [P1] Deletion & retention policy (soft/hard delete, cascade rules)
- [P1] Multi-device conflict policy (last-write-wins + state machine)
- [P1] Authorization rules (ownership enforcement)
- [P3] Promotion contract (Section 5.8)
- [P2] Task status rules + state machine (S-02, S-03)

### Invariants (Section 13)

- [P1] S-01: Canonical vs cached field classification
- [P2] S-02: Recurring task + done = invalid
- [P2] S-03: Completion state derivation
- [P2] S-04: Execution event uniqueness
- [P9] S-05: One active enrichment per type
- [P1] G-01: Edge type-pair constraints
- [P1] G-02: semantic_reference specificity
- [P1] G-03: Same-owner edge constraint
- [P1] G-04: Edge deletion cascade
- [P8] G-05: belongs_to restriction (project edges)
- [P2] T-01: No temporal-to-temporal FKs
- [P2] T-02: Append-only event records
- [P1] T-03: Temporal retention
- [P1] T-04: Ownership alignment
- [P6] D-01: Explainability requirement
- [P5] D-02: Recomputability
- [P5] D-03: Non-canonical storage
- [PC] D-04: Analytics output classification
- [P3] B-01: Promotion contract
- [P1] B-02: Deletion cascade behavior
- [P2] B-03: State machine transitions
- [P1] B-04: Background job ownership
- [P4] U-01: Max 2 unsolicited intelligence items
- [P4] U-02: Today Mode volume cap (10 items)
- [P5] U-03: Context layer volume cap (8 items)
- [P4] U-04: Per-section caps required
- [P4] U-05: Suppression precedence

### Backend Architecture (Section 8)

- [P1] FastAPI + Python domain-driven structure
- [P1] Directory layout: core/, domains/, temporal/, derived/, behavioral/
- [P1] Authorization rules at query layer
- [P1-P9] API endpoints (layer-annotated, built incrementally)

### LLM Pipeline (Section 7)

- [P9] Pipeline jobs table
- [P3] KB compilation pipeline (6-stage)
- [P9] LLM responsibilities by layer

### Sources Module (Section 6)

- [P3] Source vs Knowledge distinction
- [P3] Source inbox views (6 views by triage_status + processing_status)
- [P3] Deduplication (URL, embedding, tweet ID)
- [P3] Source edge types

### Post-MVP (Section 10)

- [PA] Browser extension for source capture
- [PB] Edge weight user override
- [PB] Memory contextual surfacing (graph first, embedding second)
- [PC] Semantic clustering, cross-node intelligence
- [PD] Habit engine, learning system, collections/spaces
- [P10] Export/import for Core entities

-----

## Phase Breakdown

### PHASE 1 — Foundation: Database + Backend Scaffold + App Shell

**Goal:** Runnable app with auth, graph infrastructure, and inbox capture.

**Backend:**

- Postgres schema setup with pgvector extension
- `users` table with basic auth (username/password, JWT tokens)
- `nodes` table with all fields (embedding as VECTOR(1536), last_accessed_at, archived_at)
  - Schema comments tagging CACHED DERIVED and BEHAVIORAL TRACKING fields (S-01)
- `edges` table with full relation_type enum (all 11 types), origin enum (user/system/llm), state enum (active/pending_review/dismissed), weight, confidence, metadata
- Edge type-pair constraint validation at application layer (G-01)
- Edge type-pair constraint trigger at database layer (G-01 safety net)
- semantic_reference specificity validation (G-02)
- Same-owner edge constraint (G-03)
- Edge deletion cascade on node hard-delete (G-04)
- `inbox_items` companion table (status: pending/promoted/dismissed/merged/archived)
- Soft delete (archived_at) + hard delete with full cascade (B-02):
  - Edges cascade-deleted
  - Temporal records flagged node_deleted=true
  - Derived caches purged
  - Pipeline jobs cancelled if pending
  - Enrichments hard-deleted
- Visibility precedence logic (archived > snoozed > stale)
- Ownership enforcement at query layer (not just API validation)
- All CRUD endpoints for nodes, edges, inbox
- FastAPI project scaffold:
  - `server/app/core/` (db, models, services: search, graph)
  - `server/app/domains/` (inbox/)
  - `server/app/temporal/`
  - `server/app/derived/`
  - `server/app/behavioral/`
- Full-text search on nodes (no embeddings yet)
- Conflict policy: last-write-wins with updated_at comparison

**Frontend:**

- Vite + React project setup
- App shell: Rail (48px, icon nav, cyan accent) + List Pane (240px, resizable) + Detail Pane
- Design tokens applied (all colors from Section 9.4)
- Typography: IBM Plex Sans + IBM Plex Mono (all contexts from 9.3)
- Cmd+K modal: search mode (default) + capture mode (Tab or >)
- Inbox domain UI: list view, detail view, status management
- Basic auth flow (login/register)
- Router with module navigation via rail

**Invariants enforced:** S-01, G-01, G-02, G-03, G-04, T-03, T-04, B-02, B-04

**API endpoints:**

- POST /api/auth/register, POST /api/auth/login
- GET/POST/PUT/DELETE /api/nodes/{id}
- GET /api/nodes/{id}/edges
- POST /api/edges
- POST /api/inbox
- GET /api/search?q=

-----

### PHASE 2 — Tasks + Journal + Execution Events + Templates

**Goal:** Core task management with execution history, journal entries, and templates.

**Backend:**

- `task_nodes` companion table (status, priority, due_date, recurrence, is_recurring, notes)
- Task status state machine with formal transition validation (B-03):
  - todo → in_progress → done (non-recurring only)
  - todo → cancelled, in_progress → cancelled
  - Recurring + done = rejected (S-02)
- `task_execution_events` temporal table (S-04: unique constraint on task_id + expected_for_date)
  - event_type: completed, skipped, deferred
  - Append-only (T-02)
  - No temporal-to-temporal FKs (T-01)
  - Ownership alignment (T-04)
- Completion state derivation logic (S-03):
  - Non-recurring: status → done when completed event exists
  - Recurring: completed event does NOT change status
- `journal_nodes` companion table (content, entry_date, mood ENUM, tags, word_count)
- `templates` table (target_type: goal/task/journal_entry, structure JSONB, is_system flag)
- Recurring task expected-date computation from cron expressions
- CRUD endpoints for tasks, journal, templates
- Task transition endpoint with state machine validation

**Frontend:**

- Tasks module: list (filterable by status/priority/due), detail pane, create/edit forms
- Task status transitions in UI (with state machine feedback)
- Recurring task indicator + execution event logging UI
- Journal module: list (by date), detail pane with markdown editor, mood selector, tags
- Templates: create, list, apply to new task/journal
- Edge creation UI: manual linking with type-pair validation, link chips in detail pane
- Basic backlinks display in detail pane

**Invariants enforced:** S-02, S-03, S-04, T-01, T-02, B-03

**API endpoints:**

- POST/GET /api/tasks, POST /api/tasks/{id}/transition
- POST/GET /api/journal
- POST/GET /api/templates
- POST/GET /api/task-execution-events

-----

### PHASE 3 — Sources + KB + Memory + Promotion

**Goal:** Full knowledge pipeline from capture through compilation to canonical knowledge.

**Backend:**

- `source_item_nodes` companion table (all fields: source_type, url, author, platform, published_at, captured_at, capture_context, raw_content, canonical_content, processing_status, triage_status, permanence, checksum, media_refs)
  - AI enrichment flat fields as temporary bridge (flagged for migration to node_enrichments)
- `source_fragments` table (fragment_text, position, fragment_type, section_ref, embedding)
- `kb_nodes` companion table (content, raw_content, compile_status 6-state, pipeline_stage 5-stage, tags, compile_version)
- `memory_nodes` companion table (memory_type enum, content, context, review_at, tags)
- Source capture workflow (4-stage: capture → normalize → enrich → promote)
- Source inbox views (6 views: All, Raw, Ready, Promoted, Dismissed, Archived)
- Source deduplication: exact URL match, embedding similarity >0.95, tweet ID
- KB compilation pipeline (6-stage: ingest → parse → compile → review → accept → stale)
- Promotion contract implementation (B-01):
  - derived_from_source edge auto-created
  - Original unchanged, state updates (triage_status → promoted)
  - Copies never moves, idempotent
  - Inbox promotion: promoted_to_node_id set, status → promoted
- Embedding service integration (flexible provider)
- Hybrid search: full-text + vector similarity
- Key indexes: IVFFlat on nodes.embedding, source_fragments.embedding, composite on edges, GIN on nodes.type, checksum index

**Frontend:**

- Sources module: list with processing_status + triage_status tabs
- Source detail pane: raw content, metadata, enrichments
- Source triage UI: promote (to KB/task/memory), dismiss, archive
- KB module: list (by compile_status), detail with markdown editor
- KB compilation UI: trigger compile, review draft, accept
- Memory module: list (by memory_type), detail pane, create/edit
- Promotion flow UI with provenance edge display

**Invariants enforced:** B-01, G-02 (semantic_reference bounded for source edges)

**API endpoints:**

- POST/GET /api/sources, POST /api/sources/{id}/promote
- POST/GET /api/kb, POST /api/kb/{id}/compile
- POST/GET /api/memory
- GET /api/search?q=&mode= (hybrid search)

-----

### PHASE 4 — Goals + Today View

**Goal:** Strategic goal tracking and the primary behavioral surface.

**Backend:**

- `goal_nodes` companion table (status enum, start_date, end_date, timeframe_label, progress CACHED DERIVED, milestones JSONB, notes)
- Goal progress computation: weighted sum of completed tasks via goal_tracks_task edges (all weights = 1.0 for MVP)
- Today View behavioral endpoint assembling:
  - Due/overdue tasks (P1)
  - Goal nudges (P4)
  - Review queue items (P5)
  - Cleanup prompts (P6)
  - Journal prompt (P7)
- Today Mode ranking policy enforcement:
  - Hard cap: 10 items
  - Per-section caps (focus 1-3, due 0-3, habits 0-2, learning 0-3, goal nudges 0-1, review 0-1, resurfaced 0-1, journal 0-1)
- Suppression rules:
  - Resurfaced only if <8 visible items
  - Goal nudges only if ≤2 urgent due items
  - Cleanup only if no active focus session
  - Journal prompt only if <7 visible items
- Max 2 unsolicited intelligence items (U-01)

**Frontend:**

- Goals module: list, detail pane with milestones, progress bar, linked tasks
- Goal creation with timeframe fields (start_date, end_date, timeframe_label)
- Today View: full-width behavioral surface (no list/detail split)
- Today View sections with visual hierarchy and per-section rendering
- Attention budget enforcement in UI

**Invariants enforced:** U-01, U-02, U-04, U-05, D-03 (progress is non-canonical)

**API endpoints:**

- POST/GET /api/goals
- GET /api/today

-----

### PHASE 5 — Derived Intelligence + Context Layer

**Goal:** Signal scores, progress metrics, retrieval modes, and the full context layer.

**Backend:**

- Signal score computation (5 factors: recency 0.3, link density 0.25, completion state 0.2, reference frequency 0.15, user interaction 0.1)
- Signal score materialized view or cache table (NOT on canonical node)
- Progress intelligence:
  - Momentum: weighted tasks completed per week (rolling 4-week avg from task_execution_events)
  - Consistency streak: consecutive days with progress
  - Drift score: 0=on track, 1=abandoned, based on time since last progress
  - Refresh: momentum + streak daily, progress on execution event
- Retrieval modes (6 modes with type weights, recency, status filters):
  - factual_qa, execution_qa, daily_briefing, reflection, improvement, link_suggestion
- Memory retrieval context layer:
  - Stage 1: explicit links via graph traversal (highest confidence, unlabeled)
  - Stage 2: suggested links via embedding similarity (thresholded, 2-3 items max, labeled “Suggested”)
  - Never mixed, one-click promotion to explicit link

**Frontend:**

- Context layer in detail pane (bottom section) with priority order:
1. Backlinks (grouped by relation type)
1. Outgoing links (weight indicators for goals)
1. Provenance / supporting sources
1. Review status / habit signals / activity
1. AI suggestions (pending edges, max 2)
1. Resurfaced content (max 2)
1. Decay flags (max 1)
- Hard cap: 8 items, target 5-8
- Suppression: if backlinks + outgoing fill 6+, suppress AI/resurfacing
- Signal score display where relevant (search results ranking)

**Invariants enforced:** U-03, U-04, D-02, D-03

-----

### PHASE 6 — Stale Detection + Cleanup System + DerivedExplanation

**Goal:** Content hygiene workflows with explainable derived outputs.

**Backend:**

- `snooze_records` temporal table (node_id, snoozed_until)
- Stale content detection per entity type:
  - task (todo): 14 days untouched
  - task (in_progress): 7 days untouched
  - goal (active): 30 days no progress
  - kb_entry (accepted): 90 days since lint
  - inbox_item (pending): 3 days unclassified
  - source_item (raw): 7 days unprocessed
- DerivedExplanation schema type:
  - summary (TEXT, required)
  - factors (JSONB[], required: [{signal, value, weight}])
  - confidence (FLOAT, optional)
  - generated_at (TIMESTAMPTZ, optional)
  - version (TEXT, optional)
- All stale flags use DerivedExplanation (D-01)
- Cleanup queue prioritization (computed at query time from stale detection + snooze_records)
- Cleanup session: one-click actions (archive, snooze with date, convert, reassign)
- Batch operations on stale items
- Review queues: stale tasks, inactive goals, unprocessed sources, low-signal KB (5-10 items per session, <90 second sessions)
- Visibility precedence: archived > snoozed > stale

**Frontend:**

- Cleanup session UI: card-based review queue
- Snooze date picker
- Batch action toolbar
- Stale indicators on list items
- DerivedExplanation display component (summary + expandable factors)

**Invariants enforced:** D-01

**API endpoints:**

- GET /api/cleanup/queue
- POST /api/cleanup/action
- POST/DELETE /api/snooze

-----

### PHASE 7 — Daily Behavior Loop (Morning Commit + Focus + Evening Reflection)

**Goal:** The full commit → execute → reflect daily cycle.

**Backend:**

- `daily_plans` temporal table (date UNIQUE, selected_task_ids[], intention_text, closed_at)
  - One plan per date, first commit wins, subsequent edits update in place
- `focus_sessions` temporal table (task_id, started_at, ended_at, duration)
- Morning commit workflow:
  - System-suggested tasks (signal score, due dates, goal drift)
  - User selects 1-3 priorities + optional secondary tasks
  - Sets intention (optional)
  - Produces daily_plans record
- Focus mode:
  - Shows only selected priorities
  - Optional timer + session tracking → focus_sessions record
- Evening reflection:
  - Compare daily_plan vs actual (join: task_execution_events via task_id + expected_for_date = daily_plans.date)
  - Quick reflection prompts
  - Output: feedback into journal + derived metrics + execution events for skipped/deferred tasks
- AI briefing stub (3-5 bullets, personalized — full AI integration in P9)

**Frontend:**

- Morning commit UI: suggested tasks, selection, intention input
- Focus mode UI: minimal view with selected priorities, timer
- Evening reflection UI: plan vs actual comparison, reflection prompts
- Today View integration: 4-stage cycle indicators (commit → execute → reflect → learn)

**API endpoints:**

- GET/POST /api/daily-plans
- GET/POST /api/focus-sessions
- POST /api/today/commit

-----

### PHASE 8 — Projects + Weekly/Monthly Reviews

**Goal:** Lightweight project containers and periodic review workflows.

**Backend:**

- `project_nodes` companion table (status: active/completed/archived, description, tags)
- belongs_to edge enforcement: goal → project, task → project only (G-05)
- `weekly_snapshots` temporal table (week_start_date, week_end_date, focus_areas TEXT[], priority_task_ids, notes)
- `monthly_snapshots` temporal table (month, focus_areas TEXT[], notes)
- Weekly review workflow:
  - System generates derived summary: completed vs planned, patterns, stalled items
  - Guided workflow: review → evaluate goals → adjust priorities → set next week focus
  - Output: weekly_snapshots record
- Monthly review workflow:
  - Same pattern, scoped to strategic questions
  - References month’s weekly snapshots
  - Output: monthly_snapshots record

**Frontend:**

- Projects module: list, detail pane, linked goals/tasks via belongs_to
- Weekly review UI: summary view + guided workflow steps
- Monthly review UI: strategic reflection view
- Project selector on goals/tasks

**Invariants enforced:** G-05

**API endpoints:**

- GET/POST /api/review/weekly
- GET/POST /api/review/monthly (add this)

-----

### PHASE 9 — AI Modes + LLM Pipeline + Enrichments

**Goal:** Full AI integration: 4 modes, enrichments, link suggestions, lint, auto-classification.

**Backend:**

- `pipeline_jobs` table (job_type enum: compile/lint/embed/suggest_links/normalize_source/enrich_source/classify_inbox, status, idempotency_key, prompt_version, model_version, retry_count)
- `node_enrichments` table (enrichment_type: summary/takeaways/entities, payload JSONB, status, prompt_version, model_version, superseded_at)
  - Current version rule: one row per node_id + enrichment_type where superseded_at IS NULL + status=completed (S-05)
  - Re-enrichment: insert new, supersede old
  - Rollback: supersede current, insert restored copy
- `ai_interaction_logs` temporal table (mode enum: ask/plan/reflect/improve, query, response_summary)
- Migrate enrichments from flat source_item_nodes fields to node_enrichments table
- Four AI modes:
  - Ask: factual_qa retrieval → answer + citations → ai_interaction_logs
  - Plan: execution_qa retrieval → suggested milestones/tasks → promotes to Core on accept
  - Reflect: reflection retrieval → narrative + patterns → derived (promotable)
  - Improve: improvement retrieval → prioritized recommendations → ai_interaction_logs
- Link suggestion: origin=llm, state=pending_review, real semantic relation_type, metadata with suggestion_rationale + confidence_explanation + supporting_signals
- KB lint pipeline (detect stale entries)
- Source auto-enrichment via node_enrichments
- Inbox auto-classification (async behavioral job)
- LLM responsibilities by layer enforced:
  - Core support: compile drafts, extract fragments
  - Derived support: summarize, rank, correlate, detect
  - Behavioral support: generate briefings, classify, reflect

**Frontend:**

- AI mode UI: Ask, Plan, Reflect, Improve panels
- Link suggestions in context layer: accept/dismiss with confidence display
- AI briefing in Today View (3-5 bullets within attention budget)
- Enrichment display on source items
- Pipeline status indicators

**Invariants enforced:** S-05, D-01 (link suggestions use DerivedExplanation)

**API endpoints:**

- POST /api/llm/ask
- POST /api/llm/plan
- POST /api/llm/reflect (add)
- POST /api/llm/improve (add)

-----

### PHASE 10 — Polish + Export/Import + Migration Cleanup

**Goal:** Performance, data portability, and architecture prep.

**Backend:**

- Performance: caching strategy, batch embedding, materialized view refresh scheduling
- Export/import for all Core entities (JSON format, preserving edges)
- Verify enrichment migration from flat fields to node_enrichments is complete
- Retention policy enforcement:
  - Pipeline jobs: 30-day cleanup for completed/failed
  - Enrichments superseded: 180-day minimum retention
- Architecture prep for Finance, Home domains (schema stubs only)

**Frontend:**

- Export/import UI
- Performance optimizations (virtualized lists, lazy loading)
- Loading states and error handling polish
- Documentation for open-source release

-----

### POST-MVP PHASE A — Browser Extension + Source Capture Expansion

**Goal:** Frictionless capture from the browser.

- Browser extension for source capture (bookmarks, articles, tweets)
- Extension → API integration
- Context-aware capture (auto-fill capture_context)

-----

### POST-MVP PHASE B — Decision Resurfacing + Edge Weights + Depth

**Goal:** Decision evaluation loops, weight controls, deeper focus mode.

- Decision resurfacing workflow:
  - Decisions with review_at due
  - Decisions with no outcome after 7d/30d/90d
  - Runs as query at load time, not scheduler
- Edge weight: optional user override (post-MVP)
- Memory contextual surfacing: graph traversal first, embedding second
- Focus mode deepened: session tracking, contextual scoping
- Cleanup system enhancements

-----

### POST-MVP PHASE C — Analytics + Intelligence

**Goal:** Full analytics dashboard and semantic intelligence.

- Analytics dashboard with 3-tier output classification:
  - Descriptive (no label): raw facts
  - Correlational (“Pattern detected”): both variables shown, never implies causation
  - Recommendation (“Suggestion”): cites underlying correlation, dismissible
- Two-tier analytics model:
  - Tier A (operational): today/7d/14d, live query
  - Tier B (trend): 30d/90d/6mo/1y, pre-aggregated rollups
- `analytics_daily_rollups` derived table (tasks_completed, tasks_planned, planning_accuracy, focus_seconds_total, focus_seconds_by_goal, journal_mood_score, streak_eligible_flag, etc.)
- `analytics_weekly_rollups` derived table (completion_rate, planning_accuracy, total_focus_time, goal_time_distribution, momentum, drift_summary, avg_mood, mood_productivity_correlation_inputs)
- Plan vs actual analysis (daily_plans + task_execution_events)
- Planning accuracy metric
- Mood / productivity correlations
- Semantic clustering (embedding similarity → topic clusters)
- Smart resurfacing:
  - Context layer (pull-based, 3-5 items, triggered on node open)
  - Today Mode (push-based, 1-2 items max, daily load)
- All analytics use DerivedExplanation schema (D-01, D-04)

-----

### POST-MVP PHASE D — Advanced (Optional)

**Goal:** Habit engine, learning system, collections.

- Habit engine: daily routines, habit tracking, adaptive suggestions (uses task_execution_events history)
- Learning system: structured learning paths, spaced repetition
- Collections / spaces: flexible cross-type groupings

-----

## Phase Dependency Graph

```
P1 (Foundation)
├── P2 (Tasks + Journal + Events)
│   ├── P3 (Sources + KB + Memory)
│   │   └── P4 (Goals + Today View)
│   │       ├── P5 (Derived Intelligence + Context Layer)
│   │       │   ├── P6 (Stale Detection + Cleanup)
│   │       │   │   └── P7 (Daily Behavior Loop)
│   │       │   │       └── P8 (Projects + Reviews)
│   │       │   └── P9 (AI Modes + LLM Pipeline)
│   │       └── P9 (AI Modes + LLM Pipeline)
│   └── P7 (Daily Behavior Loop)
└── P10 (Polish + Export)

Post-MVP:
PA (Browser Extension) — after P3
PB (Decision Resurfacing + Weights) — after P9
PC (Analytics) — after P8 + P9
PD (Habits + Learning) — after PC
```

## Prompt Strategy

Each phase above becomes **one implementation prompt**. Each prompt will include:

1. **Exact schema** (SQL CREATE statements with all columns, types, constraints, comments)
1. **Backend code** (FastAPI routes, services, models, validation logic)
1. **Frontend code** (React components, state management, API integration)
1. **Invariant enforcement** (which invariants apply, how they’re tested)
1. **API contract** (request/response shapes)

Total: **10 MVP prompts + 4 post-MVP prompts = 14 prompts**