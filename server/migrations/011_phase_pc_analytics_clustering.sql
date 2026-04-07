-- Phase PC: Analytics + Intelligence
-- Analytics rollup tables (Derived layer), semantic clustering, smart resurfacing
--
-- Invariant D-02: All tables are fully recomputable from Core + Temporal data.
-- Invariant D-03: Non-canonical storage — never treated as source of truth.
-- Invariant D-04: Analytics output classification (descriptive/correlational/recommendation).

-- =============================================================================
-- analytics_daily_rollups (Section 4.7 — Derived Layer)
-- Pre-aggregated daily metrics for Tier B analytics (30d+ time ranges).
-- All values are CACHED DERIVED and recomputable from Core + Temporal data.
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_daily_rollups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,

    -- Task metrics (from task_execution_events)
    tasks_completed         INTEGER NOT NULL DEFAULT 0,
    tasks_planned           INTEGER NOT NULL DEFAULT 0,
    tasks_planned_completed INTEGER NOT NULL DEFAULT 0,
    planning_accuracy       FLOAT NOT NULL DEFAULT 0.0,

    -- Focus metrics (from focus_sessions)
    focus_seconds_total     INTEGER NOT NULL DEFAULT 0,
    focus_seconds_by_goal   JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Journal metrics (from journal_nodes)
    journal_mood_score      FLOAT,  -- NULL if no journal entry; maps great=5,good=4,neutral=3,low=2,bad=1

    -- Goal metrics (from progress_intelligence)
    active_goal_progress_delta FLOAT NOT NULL DEFAULT 0.0,

    -- Streak metric
    streak_eligible_flag    BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, date)
);

COMMENT ON TABLE analytics_daily_rollups IS 'CACHED DERIVED: Pre-aggregated daily analytics. Invariant D-02: recomputable, D-03: non-canonical, D-04: analytics output classification.';
COMMENT ON COLUMN analytics_daily_rollups.tasks_completed IS 'CACHED DERIVED: Count of completed task_execution_events for this date.';
COMMENT ON COLUMN analytics_daily_rollups.tasks_planned IS 'CACHED DERIVED: Count of tasks in daily_plans.selected_task_ids for this date.';
COMMENT ON COLUMN analytics_daily_rollups.tasks_planned_completed IS 'CACHED DERIVED: Tasks that were both planned and completed.';
COMMENT ON COLUMN analytics_daily_rollups.planning_accuracy IS 'CACHED DERIVED: tasks_planned_completed / tasks_planned (0 if no plan).';
COMMENT ON COLUMN analytics_daily_rollups.focus_seconds_total IS 'CACHED DERIVED: Sum of focus_sessions.duration for this date.';
COMMENT ON COLUMN analytics_daily_rollups.focus_seconds_by_goal IS 'CACHED DERIVED: JSONB mapping goal_id -> focus seconds via goal_tracks_task edges.';
COMMENT ON COLUMN analytics_daily_rollups.journal_mood_score IS 'CACHED DERIVED: Numeric mood score (great=5..bad=1) from journal entry, NULL if none.';
COMMENT ON COLUMN analytics_daily_rollups.active_goal_progress_delta IS 'CACHED DERIVED: Net change in active goal progress for this date.';
COMMENT ON COLUMN analytics_daily_rollups.streak_eligible_flag IS 'CACHED DERIVED: Whether this day counts toward a consistency streak.';

CREATE INDEX idx_analytics_daily_user ON analytics_daily_rollups(user_id);
CREATE INDEX idx_analytics_daily_date ON analytics_daily_rollups(date);
CREATE INDEX idx_analytics_daily_user_date ON analytics_daily_rollups(user_id, date);


-- =============================================================================
-- analytics_weekly_rollups (Section 4.7 — Derived Layer)
-- Pre-aggregated weekly metrics for Tier B analytics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_weekly_rollups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start_date DATE NOT NULL,  -- Monday of the week

    -- Aggregated task metrics
    completion_rate         FLOAT NOT NULL DEFAULT 0.0,
    planning_accuracy       FLOAT NOT NULL DEFAULT 0.0,

    -- Focus metrics
    total_focus_time        INTEGER NOT NULL DEFAULT 0,  -- seconds
    goal_time_distribution  JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Progress metrics (from progress_intelligence)
    momentum                FLOAT NOT NULL DEFAULT 0.0,
    drift_summary           JSONB NOT NULL DEFAULT '[]'::JSONB,  -- [{goal_id, drift_score}]

    -- Wellbeing metrics
    avg_mood                FLOAT,  -- NULL if no journal entries
    mood_productivity_correlation_inputs JSONB NOT NULL DEFAULT '[]'::JSONB,
        -- [{date, mood_score, tasks_completed, focus_seconds}] for correlation computation

    -- Metadata
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(user_id, week_start_date)
);

COMMENT ON TABLE analytics_weekly_rollups IS 'CACHED DERIVED: Pre-aggregated weekly analytics. Invariant D-02: recomputable, D-03: non-canonical, D-04: analytics output classification.';
COMMENT ON COLUMN analytics_weekly_rollups.completion_rate IS 'CACHED DERIVED: tasks_completed / tasks_planned across the week.';
COMMENT ON COLUMN analytics_weekly_rollups.planning_accuracy IS 'CACHED DERIVED: Average daily planning_accuracy across the week.';
COMMENT ON COLUMN analytics_weekly_rollups.total_focus_time IS 'CACHED DERIVED: Sum of focus_seconds_total from daily rollups.';
COMMENT ON COLUMN analytics_weekly_rollups.goal_time_distribution IS 'CACHED DERIVED: JSONB mapping goal_id -> total focus seconds for the week.';
COMMENT ON COLUMN analytics_weekly_rollups.momentum IS 'CACHED DERIVED: Weighted tasks completed per week (rolling 4-week avg).';
COMMENT ON COLUMN analytics_weekly_rollups.drift_summary IS 'CACHED DERIVED: JSONB array of {goal_id, drift_score} for active goals.';
COMMENT ON COLUMN analytics_weekly_rollups.avg_mood IS 'CACHED DERIVED: Average mood score across journal entries for the week.';
COMMENT ON COLUMN analytics_weekly_rollups.mood_productivity_correlation_inputs IS 'CACHED DERIVED: Raw inputs for mood-productivity correlation analysis.';

CREATE INDEX idx_analytics_weekly_user ON analytics_weekly_rollups(user_id);
CREATE INDEX idx_analytics_weekly_date ON analytics_weekly_rollups(week_start_date);
CREATE INDEX idx_analytics_weekly_user_date ON analytics_weekly_rollups(user_id, week_start_date);


-- =============================================================================
-- semantic_clusters (Section 4.9 — Derived Layer)
-- Auto-detected topic clusters using embedding similarity.
-- =============================================================================

CREATE TABLE IF NOT EXISTS semantic_clusters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,          -- Auto-generated cluster label
    centroid        vector(1536),           -- Cluster centroid embedding
    node_count      INTEGER NOT NULL DEFAULT 0,
    coherence_score FLOAT NOT NULL DEFAULT 0.0,  -- How tight the cluster is (0-1)
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version         TEXT DEFAULT 'v1'
);

COMMENT ON TABLE semantic_clusters IS 'CACHED DERIVED: Auto-detected topic clusters via embedding similarity. Invariant D-02: recomputable, D-03: non-canonical.';
COMMENT ON COLUMN semantic_clusters.centroid IS 'CACHED DERIVED: Average embedding of cluster members.';
COMMENT ON COLUMN semantic_clusters.coherence_score IS 'CACHED DERIVED: Intra-cluster similarity (0=dispersed, 1=tight).';

CREATE INDEX idx_semantic_clusters_user ON semantic_clusters(user_id);


-- =============================================================================
-- semantic_cluster_members (Section 4.9 — Derived Layer)
-- Membership table linking nodes to clusters.
-- =============================================================================

CREATE TABLE IF NOT EXISTS semantic_cluster_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id      UUID NOT NULL REFERENCES semantic_clusters(id) ON DELETE CASCADE,
    node_id         UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    similarity      FLOAT NOT NULL DEFAULT 0.0,  -- Similarity to cluster centroid
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE(cluster_id, node_id)
);

COMMENT ON TABLE semantic_cluster_members IS 'CACHED DERIVED: Node-to-cluster membership. Invariant D-02: recomputable, D-03: non-canonical.';
COMMENT ON COLUMN semantic_cluster_members.similarity IS 'CACHED DERIVED: Cosine similarity between node embedding and cluster centroid.';

CREATE INDEX idx_cluster_members_cluster ON semantic_cluster_members(cluster_id);
CREATE INDEX idx_cluster_members_node ON semantic_cluster_members(node_id);
