-- Personal OS Phase 4: Goals + Today View
-- Implements: goal_nodes companion table
-- Invariants: U-01 (max 2 unsolicited), U-02 (10-item cap), U-04 (per-section caps),
--             U-05 (suppression precedence), D-03 (progress is non-canonical)

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Goal status (Section 2.4)
CREATE TYPE goal_status AS ENUM ('active', 'completed', 'archived');

-- =============================================================================
-- GOAL_NODES COMPANION TABLE (Section 2.4)
-- =============================================================================
-- Goals are strategic objectives that track progress via linked tasks.
-- Progress is a CACHED DERIVED field computed from goal_tracks_task edges.
-- Invariant D-03: progress is non-canonical, stored for display convenience only.

CREATE TABLE goal_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,

    -- Goal lifecycle
    status goal_status NOT NULL DEFAULT 'active',

    -- Timeframe
    start_date DATE,
    end_date DATE,
    timeframe_label TEXT,  -- e.g. "Q1 2026", "This month", "Long-term"

    -- CACHED DERIVED: Weighted sum of completed tasks via goal_tracks_task edges.
    -- All weights = 1.0 for MVP. Invariant D-03: Non-canonical, recomputable.
    -- Invariant S-01: CACHED DERIVED field.
    progress FLOAT NOT NULL DEFAULT 0.0,

    -- Structured milestones
    milestones JSONB DEFAULT '[]'::jsonb,

    -- Notes
    notes TEXT
);

COMMENT ON COLUMN goal_nodes.progress IS 'CACHED DERIVED: Weighted sum of completed tasks via goal_tracks_task edges. Non-canonical (D-03). Invariant S-01.';

-- Indexes
CREATE INDEX idx_goal_nodes_status ON goal_nodes(status);
CREATE INDEX idx_goal_nodes_end_date ON goal_nodes(end_date) WHERE end_date IS NOT NULL;

-- =============================================================================
-- CHECK CONSTRAINT: progress range
-- =============================================================================
ALTER TABLE goal_nodes ADD CONSTRAINT goal_progress_range CHECK (progress >= 0.0 AND progress <= 1.0);
