-- Phase 9: AI Modes + LLM Pipeline + Enrichments
-- Tables: pipeline_jobs, node_enrichments, ai_interaction_logs
-- Invariant S-05: One active enrichment per type (partial unique index)
-- Migrate enrichments from flat source_item_nodes fields to node_enrichments

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE pipeline_job_type AS ENUM (
    'compile', 'lint', 'embed', 'suggest_links',
    'normalize_source', 'enrich_source', 'classify_inbox'
);

CREATE TYPE pipeline_job_status AS ENUM (
    'pending', 'running', 'completed', 'failed', 'cancelled'
);

CREATE TYPE enrichment_type AS ENUM (
    'summary', 'takeaways', 'entities'
);

CREATE TYPE enrichment_status AS ENUM (
    'pending', 'processing', 'completed', 'failed'
);

CREATE TYPE ai_mode AS ENUM (
    'ask', 'plan', 'reflect', 'improve'
);

-- =============================================================================
-- pipeline_jobs (Section 7.3)
-- Tracks all LLM pipeline operations with idempotency and retry support.
-- =============================================================================

CREATE TABLE pipeline_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Invariant B-04: Pipeline jobs inherit ownership from their target node
    target_node_id UUID REFERENCES nodes(id) ON DELETE SET NULL,
    job_type pipeline_job_type NOT NULL,
    status pipeline_job_status NOT NULL DEFAULT 'pending',
    idempotency_key TEXT,
    prompt_version TEXT,
    model_version TEXT,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Idempotency: prevent duplicate jobs
CREATE UNIQUE INDEX idx_pipeline_jobs_idempotency
    ON pipeline_jobs(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX idx_pipeline_jobs_status ON pipeline_jobs(status);
CREATE INDEX idx_pipeline_jobs_type ON pipeline_jobs(job_type);
CREATE INDEX idx_pipeline_jobs_user ON pipeline_jobs(user_id);
CREATE INDEX idx_pipeline_jobs_target ON pipeline_jobs(target_node_id)
    WHERE target_node_id IS NOT NULL;
CREATE INDEX idx_pipeline_jobs_created ON pipeline_jobs(created_at);

COMMENT ON TABLE pipeline_jobs IS 'Section 7.3: LLM pipeline job tracking with idempotency. Retention: 30-day cleanup for completed/failed.';

-- =============================================================================
-- node_enrichments (Section 4.8)
-- Versioned enrichment table replacing flat AI fields on source_item_nodes.
-- Invariant S-05: One active enrichment per type enforced via partial unique index.
-- =============================================================================

CREATE TABLE node_enrichments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    enrichment_type enrichment_type NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    status enrichment_status NOT NULL DEFAULT 'pending',
    prompt_version TEXT,
    model_version TEXT,
    -- Versioning: superseded_at NULL = current version
    superseded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Reference to pipeline job that created this enrichment
    pipeline_job_id UUID REFERENCES pipeline_jobs(id) ON DELETE SET NULL
);

-- Invariant S-05: Only one active (non-superseded, completed) enrichment per node+type
CREATE UNIQUE INDEX idx_node_enrichments_active
    ON node_enrichments(node_id, enrichment_type)
    WHERE superseded_at IS NULL AND status = 'completed';

CREATE INDEX idx_node_enrichments_node ON node_enrichments(node_id);
CREATE INDEX idx_node_enrichments_type ON node_enrichments(enrichment_type);
CREATE INDEX idx_node_enrichments_status ON node_enrichments(status);
CREATE INDEX idx_node_enrichments_superseded ON node_enrichments(superseded_at)
    WHERE superseded_at IS NOT NULL;

COMMENT ON TABLE node_enrichments IS 'Section 4.8: Versioned AI enrichments. Invariant S-05: one active enrichment per node_id + enrichment_type where superseded_at IS NULL + status=completed.';
COMMENT ON COLUMN node_enrichments.superseded_at IS 'NULL = current version. Non-NULL = replaced by newer enrichment. Retention: 180+ days minimum.';

-- =============================================================================
-- ai_interaction_logs (Section 3.6 — Temporal layer)
-- Temporal table for AI mode interaction history.
-- Invariant T-01: No temporal-to-temporal FKs.
-- Invariant T-04: user_id must match owner_id of referenced nodes.
-- =============================================================================

CREATE TABLE ai_interaction_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode ai_mode NOT NULL,
    query TEXT NOT NULL,
    response_summary TEXT,
    -- Full response stored for audit
    response_data JSONB DEFAULT '{}',
    -- Context: which nodes were retrieved for this interaction
    context_node_ids UUID[] DEFAULT '{}',
    -- Duration tracking
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Invariant T-03: node_deleted flag for retention
    node_deleted BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX idx_ai_interaction_logs_user ON ai_interaction_logs(user_id);
CREATE INDEX idx_ai_interaction_logs_mode ON ai_interaction_logs(mode);
CREATE INDEX idx_ai_interaction_logs_created ON ai_interaction_logs(created_at);

COMMENT ON TABLE ai_interaction_logs IS 'Section 3.6: Temporal table for AI mode interaction history. Invariant T-01: no temporal-to-temporal FKs. Invariant T-04: ownership alignment.';

-- =============================================================================
-- Migrate existing flat enrichment fields from source_item_nodes
-- Copy existing ai_summary, ai_takeaways, ai_entities to node_enrichments
-- =============================================================================

-- Migrate ai_summary
INSERT INTO node_enrichments (node_id, enrichment_type, payload, status, prompt_version, created_at)
SELECT
    node_id,
    'summary'::enrichment_type,
    jsonb_build_object('text', ai_summary),
    'completed'::enrichment_status,
    'migrated_from_flat_fields',
    now()
FROM source_item_nodes
WHERE ai_summary IS NOT NULL;

-- Migrate ai_takeaways
INSERT INTO node_enrichments (node_id, enrichment_type, payload, status, prompt_version, created_at)
SELECT
    node_id,
    'takeaways'::enrichment_type,
    jsonb_build_object('items', ai_takeaways),
    'completed'::enrichment_status,
    'migrated_from_flat_fields',
    now()
FROM source_item_nodes
WHERE ai_takeaways IS NOT NULL;

-- Migrate ai_entities
INSERT INTO node_enrichments (node_id, enrichment_type, payload, status, prompt_version, created_at)
SELECT
    node_id,
    'entities'::enrichment_type,
    jsonb_build_object('items', ai_entities),
    'completed'::enrichment_status,
    'migrated_from_flat_fields',
    now()
FROM source_item_nodes
WHERE ai_entities IS NOT NULL;

-- Note: Flat fields on source_item_nodes are retained for backward compatibility
-- but should no longer be written to. New enrichments go to node_enrichments.
