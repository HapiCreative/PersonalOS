-- Phase 10: Polish + Export/Import + Retention Policy + Migration Cleanup
-- 1. Finalize enrichment migration: drop flat AI fields from source_item_nodes
-- 2. Retention policy indexes for cleanup jobs
-- 3. Architecture prep: finance_nodes, home_nodes schema stubs
-- 4. Materialized view for signal score caching

-- =============================================================================
-- 1. ENRICHMENT MIGRATION COMPLETION
-- Section 4.8: Enrichments now fully live in node_enrichments table.
-- The flat ai_summary, ai_takeaways, ai_entities columns on source_item_nodes
-- were a temporary bridge (Phase 3/9). Data was migrated in migration 009.
-- =============================================================================

-- Drop the deprecated flat enrichment columns from source_item_nodes
ALTER TABLE source_item_nodes DROP COLUMN IF EXISTS ai_summary;
ALTER TABLE source_item_nodes DROP COLUMN IF EXISTS ai_takeaways;
ALTER TABLE source_item_nodes DROP COLUMN IF EXISTS ai_entities;

COMMENT ON TABLE source_item_nodes IS 'Section 2.4 / Section 6: Source items. AI enrichment fields migrated to node_enrichments (Phase 10).';

-- =============================================================================
-- 2. RETENTION POLICY INDEXES
-- Section 1.7: Retention Defaults
--   - Pipeline jobs: 30-day cleanup for completed/failed
--   - Enrichments superseded: 180-day minimum retention
-- =============================================================================

-- Index for efficient retention cleanup queries on pipeline_jobs
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_retention
    ON pipeline_jobs(completed_at)
    WHERE status IN ('completed', 'failed') AND completed_at IS NOT NULL;

-- Index for efficient superseded enrichment retention queries
CREATE INDEX IF NOT EXISTS idx_node_enrichments_retention
    ON node_enrichments(superseded_at)
    WHERE superseded_at IS NOT NULL;

COMMENT ON INDEX idx_pipeline_jobs_retention IS 'Phase 10: Supports 30-day retention cleanup for completed/failed pipeline jobs.';
COMMENT ON INDEX idx_node_enrichments_retention IS 'Phase 10: Supports 180-day retention cleanup for superseded enrichments.';

-- =============================================================================
-- 3. MATERIALIZED VIEW FOR SIGNAL SCORE CACHING
-- Section 4.1: Signal scores cached in materialized view for performance.
-- Invariant D-02: Recomputable from Core + Temporal data.
-- Invariant D-03: Non-canonical storage for query convenience.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_signal_scores AS
SELECT
    n.id AS node_id,
    n.type AS node_type,
    n.owner_id,
    -- Recency factor (0-1): exponential decay based on days since update
    GREATEST(0, 1.0 - (EXTRACT(EPOCH FROM (now() - n.updated_at)) / (86400.0 * 90))) AS recency_score,
    -- Link density: count of active edges
    COALESCE(edge_counts.edge_count, 0) AS edge_count,
    LEAST(1.0, COALESCE(edge_counts.edge_count, 0) / 10.0) AS link_density_score,
    -- Computed at timestamp
    now() AS computed_at
FROM nodes n
LEFT JOIN (
    SELECT
        node_id,
        COUNT(*) AS edge_count
    FROM (
        SELECT source_id AS node_id FROM edges WHERE state = 'active'
        UNION ALL
        SELECT target_id AS node_id FROM edges WHERE state = 'active'
    ) all_edges
    GROUP BY node_id
) edge_counts ON edge_counts.node_id = n.id
WHERE n.archived_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_signal_scores_node
    ON mv_signal_scores(node_id);

COMMENT ON MATERIALIZED VIEW mv_signal_scores IS 'Phase 10: Cached signal scores. Invariant D-02: recomputable. Invariant D-03: non-canonical.';

-- =============================================================================
-- 4. ARCHITECTURE PREP: FINANCE + HOME DOMAIN STUBS
-- Section 11: Future Expansion Framework
-- These are schema stubs only — no application code until future phases.
-- =============================================================================

-- Finance domain stub
CREATE TYPE finance_entry_type AS ENUM (
    'income', 'expense', 'transfer', 'investment'
);

CREATE TYPE finance_category AS ENUM (
    'housing', 'transportation', 'food', 'utilities',
    'insurance', 'healthcare', 'savings', 'personal',
    'entertainment', 'education', 'charity', 'other'
);

CREATE TABLE finance_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    entry_type finance_entry_type NOT NULL,
    category finance_category NOT NULL DEFAULT 'other',
    amount NUMERIC(12, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    entry_date DATE NOT NULL,
    vendor TEXT,
    notes TEXT,
    is_recurring BOOLEAN NOT NULL DEFAULT false,
    recurrence TEXT -- cron expression, same format as task_nodes
);

CREATE INDEX idx_finance_nodes_type ON finance_nodes(entry_type);
CREATE INDEX idx_finance_nodes_date ON finance_nodes(entry_date);
CREATE INDEX idx_finance_nodes_category ON finance_nodes(category);

COMMENT ON TABLE finance_nodes IS 'Phase 10 STUB: Future finance domain. Schema only, no application code yet. Section 11: Feature Admission Rules.';

-- Home domain stub
CREATE TYPE home_item_type AS ENUM (
    'maintenance', 'inventory', 'project', 'warranty', 'utility'
);

CREATE TYPE home_urgency AS ENUM (
    'routine', 'soon', 'urgent', 'emergency'
);

CREATE TABLE home_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    item_type home_item_type NOT NULL,
    location TEXT,
    urgency home_urgency NOT NULL DEFAULT 'routine',
    due_date DATE,
    completed_at TIMESTAMPTZ,
    cost NUMERIC(10, 2),
    notes TEXT
);

CREATE INDEX idx_home_nodes_type ON home_nodes(item_type);
CREATE INDEX idx_home_nodes_due ON home_nodes(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX idx_home_nodes_urgency ON home_nodes(urgency);

COMMENT ON TABLE home_nodes IS 'Phase 10 STUB: Future home management domain. Schema only, no application code yet. Section 11: Feature Admission Rules.';
