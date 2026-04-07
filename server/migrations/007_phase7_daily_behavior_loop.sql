-- Phase 7: Daily Behavior Loop (Morning Commit + Focus + Evening Reflection)
-- Tables: daily_plans, focus_sessions (Temporal layer, Section 3)
--
-- Invariant T-01: No temporal-to-temporal FKs (both tables reference Core only)
-- Invariant T-04: Ownership alignment (user_id FK → users)

-- =============================================================================
-- TABLE: daily_plans (Section 3 — TABLE 22)
-- One plan per user per date. First commit wins; subsequent edits update in place.
-- =============================================================================
CREATE TABLE IF NOT EXISTS daily_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    selected_task_ids UUID[] NOT NULL DEFAULT '{}',
    intention_text  TEXT,                           -- Optional daily intention
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ,                    -- End-of-day closure timestamp

    -- One plan per user per date
    CONSTRAINT uq_daily_plans_user_date UNIQUE (user_id, date)
);

-- Indexes for daily_plans
CREATE INDEX IF NOT EXISTS idx_daily_plans_user    ON daily_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_plans_date    ON daily_plans(date);

COMMENT ON TABLE daily_plans IS 'Temporal: daily commitment record (Section 3). One per user per date.';
COMMENT ON COLUMN daily_plans.selected_task_ids IS 'Task node IDs chosen for the day (references nodes.id)';
COMMENT ON COLUMN daily_plans.intention_text IS 'Optional daily intention text';
COMMENT ON COLUMN daily_plans.closed_at IS 'When the plan was closed (evening reflection)';


-- =============================================================================
-- TABLE: focus_sessions (Section 3 — TABLE 25)
-- Timed work sessions linked to a task. Append-only temporal records.
-- =============================================================================
CREATE TABLE IF NOT EXISTS focus_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id         UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at        TIMESTAMPTZ,                    -- NULL if session still active
    duration        INTEGER,                        -- Duration in seconds (computed on end)

    -- Invariant T-01: Only references Core entities (users, nodes), no temporal FKs
    CONSTRAINT chk_focus_session_duration CHECK (duration IS NULL OR duration >= 0)
);

-- Indexes for focus_sessions
CREATE INDEX IF NOT EXISTS idx_focus_sessions_user     ON focus_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_focus_sessions_task     ON focus_sessions(task_id);
CREATE INDEX IF NOT EXISTS idx_focus_sessions_started  ON focus_sessions(started_at);

COMMENT ON TABLE focus_sessions IS 'Temporal: timed focus work sessions (Section 3). Append-only.';
COMMENT ON COLUMN focus_sessions.task_id IS 'Task being focused on (FK → nodes.id)';
COMMENT ON COLUMN focus_sessions.duration IS 'Duration in seconds, computed when session ends';
