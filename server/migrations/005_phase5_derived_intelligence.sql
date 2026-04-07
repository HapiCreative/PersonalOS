-- Personal OS Phase 5: Derived Intelligence + Context Layer
-- Implements: Signal score cache, progress intelligence cache
-- Invariants: U-03 (context layer 8-item cap), D-02 (recomputability),
--             D-03 (non-canonical storage)

-- =============================================================================
-- SIGNAL SCORE CACHE TABLE (Section 4 — Derived Layer)
-- =============================================================================
-- Invariant D-03: Non-canonical, stored for display/ranking convenience only.
-- Invariant D-02: Fully recomputable from Core + Temporal data.
-- NOT on the canonical node — separate derived table.
-- 5 factors: recency (0.3), link_density (0.25), completion_state (0.2),
--            reference_frequency (0.15), user_interaction (0.1)

CREATE TABLE signal_scores (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,

    -- Composite score (0.0 to 1.0)
    score FLOAT NOT NULL DEFAULT 0.0,

    -- Individual factor scores (each 0.0 to 1.0)
    recency_score FLOAT NOT NULL DEFAULT 0.0,
    link_density_score FLOAT NOT NULL DEFAULT 0.0,
    completion_state_score FLOAT NOT NULL DEFAULT 0.0,
    reference_frequency_score FLOAT NOT NULL DEFAULT 0.0,
    user_interaction_score FLOAT NOT NULL DEFAULT 0.0,

    -- Metadata
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version TEXT DEFAULT 'v1'
);

COMMENT ON TABLE signal_scores IS 'DERIVED (D-03): Signal score cache. Non-canonical, recomputable (D-02). 5-factor composite score for ranking and relevance.';
COMMENT ON COLUMN signal_scores.score IS 'CACHED DERIVED: Weighted composite of 5 factors. Invariant D-03.';
COMMENT ON COLUMN signal_scores.recency_score IS 'CACHED DERIVED: Factor weight 0.3. Based on updated_at recency.';
COMMENT ON COLUMN signal_scores.link_density_score IS 'CACHED DERIVED: Factor weight 0.25. Based on edge count.';
COMMENT ON COLUMN signal_scores.completion_state_score IS 'CACHED DERIVED: Factor weight 0.2. Based on task/goal status.';
COMMENT ON COLUMN signal_scores.reference_frequency_score IS 'CACHED DERIVED: Factor weight 0.15. Based on incoming edge count.';
COMMENT ON COLUMN signal_scores.user_interaction_score IS 'CACHED DERIVED: Factor weight 0.1. Based on last_accessed_at recency.';

-- Indexes
CREATE INDEX idx_signal_scores_score ON signal_scores(score DESC);
CREATE INDEX idx_signal_scores_computed ON signal_scores(computed_at);

-- Check constraints
ALTER TABLE signal_scores ADD CONSTRAINT signal_score_range CHECK (score >= 0.0 AND score <= 1.0);
ALTER TABLE signal_scores ADD CONSTRAINT signal_recency_range CHECK (recency_score >= 0.0 AND recency_score <= 1.0);
ALTER TABLE signal_scores ADD CONSTRAINT signal_link_density_range CHECK (link_density_score >= 0.0 AND link_density_score <= 1.0);
ALTER TABLE signal_scores ADD CONSTRAINT signal_completion_range CHECK (completion_state_score >= 0.0 AND completion_state_score <= 1.0);
ALTER TABLE signal_scores ADD CONSTRAINT signal_reference_range CHECK (reference_frequency_score >= 0.0 AND reference_frequency_score <= 1.0);
ALTER TABLE signal_scores ADD CONSTRAINT signal_interaction_range CHECK (user_interaction_score >= 0.0 AND user_interaction_score <= 1.0);


-- =============================================================================
-- PROGRESS INTELLIGENCE CACHE TABLE (Section 4 — Derived Layer)
-- =============================================================================
-- Tracks momentum, consistency, and drift for goals and tasks.
-- Invariant D-03: Non-canonical, recomputable from task_execution_events + edges.
-- Invariant D-02: Fully recomputable.

CREATE TABLE progress_intelligence (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,

    -- Progress (for goals: weighted task completion ratio)
    progress FLOAT NOT NULL DEFAULT 0.0,

    -- Momentum: weighted tasks completed per week (rolling 4-week avg from task_execution_events)
    momentum FLOAT NOT NULL DEFAULT 0.0,

    -- Consistency streak: consecutive days with progress
    consistency_streak INT NOT NULL DEFAULT 0,

    -- Drift score: 0=on track, 1=abandoned, based on time since last progress
    drift_score FLOAT NOT NULL DEFAULT 0.0,

    -- Last progress timestamp (for drift calculation)
    last_progress_at TIMESTAMPTZ,

    -- Metadata
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    version TEXT DEFAULT 'v1'
);

COMMENT ON TABLE progress_intelligence IS 'DERIVED (D-03): Progress intelligence cache. Non-canonical, recomputable (D-02). Tracks momentum, consistency, and drift.';
COMMENT ON COLUMN progress_intelligence.progress IS 'CACHED DERIVED: Goal/task progress ratio. Invariant D-03.';
COMMENT ON COLUMN progress_intelligence.momentum IS 'CACHED DERIVED: Weighted tasks completed per week (rolling 4-week avg). Invariant D-03.';
COMMENT ON COLUMN progress_intelligence.consistency_streak IS 'CACHED DERIVED: Consecutive days with progress. Invariant D-03.';
COMMENT ON COLUMN progress_intelligence.drift_score IS 'CACHED DERIVED: 0=on track, 1=abandoned. Based on time since last progress. Invariant D-03.';

-- Indexes
CREATE INDEX idx_progress_intelligence_momentum ON progress_intelligence(momentum DESC);
CREATE INDEX idx_progress_intelligence_drift ON progress_intelligence(drift_score DESC);
CREATE INDEX idx_progress_intelligence_streak ON progress_intelligence(consistency_streak DESC);

-- Check constraints
ALTER TABLE progress_intelligence ADD CONSTRAINT progress_range CHECK (progress >= 0.0 AND progress <= 1.0);
ALTER TABLE progress_intelligence ADD CONSTRAINT momentum_range CHECK (momentum >= 0.0);
ALTER TABLE progress_intelligence ADD CONSTRAINT streak_range CHECK (consistency_streak >= 0);
ALTER TABLE progress_intelligence ADD CONSTRAINT drift_range CHECK (drift_score >= 0.0 AND drift_score <= 1.0);
