-- Phase PB: Decision Resurfacing + Edge Weights + Depth
-- No new tables required — all features build on existing schema:
-- - Decision resurfacing: queries memory_nodes (memory_type='decision') + review_at
-- - Edge weight override: uses existing edges.weight column (0.0-1.0)
-- - Memory contextual surfacing: uses existing edges + nodes.embedding
-- - Focus mode deepening: uses existing focus_sessions table
-- - Cleanup enhancements: uses existing nodes + edges tables

-- Add index for decision resurfacing queries (memory_type + review_at)
CREATE INDEX IF NOT EXISTS idx_memory_nodes_decision_review
    ON memory_nodes (memory_type, review_at)
    WHERE memory_type = 'decision';

-- Add index for focus session stats queries
CREATE INDEX IF NOT EXISTS idx_focus_sessions_user_started
    ON focus_sessions (user_id, started_at)
    WHERE ended_at IS NOT NULL;

-- Comment: Phase PB features are purely behavioral/derived layer additions
-- that operate on existing Core, Temporal, and Derived infrastructure.
