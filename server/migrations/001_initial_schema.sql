-- Personal OS Phase 1: Foundation Schema
-- Implements: users, nodes, edges, inbox_items
-- Invariants: S-01, G-01, G-02, G-03, G-04, T-03, T-04, B-02, B-04

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Node types (all Core entity types from Section 2.2)
CREATE TYPE node_type AS ENUM (
    'kb_entry', 'task', 'journal_entry', 'goal', 'memory',
    'source_item', 'inbox_item', 'project'
);

-- Edge relation types (Section 2.3 - all 11 types)
CREATE TYPE edge_relation_type AS ENUM (
    'semantic_reference', 'derived_from_source', 'parent_child',
    'belongs_to', 'goal_tracks_task', 'goal_tracks_kb', 'blocked_by',
    'journal_reflects_on', 'source_supports_goal', 'source_quoted_in',
    'captured_for'
);

-- Edge origin (Section 2.3)
CREATE TYPE edge_origin AS ENUM ('user', 'system', 'llm');

-- Edge state (Section 2.3)
CREATE TYPE edge_state AS ENUM ('active', 'pending_review', 'dismissed');

-- Inbox item status (Section 2.4 - inbox_items)
CREATE TYPE inbox_item_status AS ENUM (
    'pending', 'promoted', 'dismissed', 'merged', 'archived'
);

-- =============================================================================
-- USERS TABLE (Section 2.1)
-- =============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- NODES TABLE (Section 2.2 - Graph Identity Layer)
-- =============================================================================

CREATE TABLE nodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    type node_type NOT NULL,
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT,
    -- Invariant S-01: CACHED DERIVED - semantic embedding, recomputable
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Invariant S-01: BEHAVIORAL TRACKING - last viewed, for decay detection
    last_accessed_at TIMESTAMPTZ,
    archived_at TIMESTAMPTZ
);

COMMENT ON COLUMN nodes.embedding IS 'CACHED DERIVED: Semantic embedding, recomputable from content. Invariant S-01.';
COMMENT ON COLUMN nodes.last_accessed_at IS 'BEHAVIORAL TRACKING: Last viewed timestamp for decay detection. Invariant S-01.';

-- =============================================================================
-- EDGES TABLE (Section 2.3)
-- =============================================================================

CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation_type edge_relation_type NOT NULL,
    origin edge_origin NOT NULL DEFAULT 'user',
    state edge_state NOT NULL DEFAULT 'active',
    weight FLOAT NOT NULL DEFAULT 1.0,
    confidence FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT edges_weight_range CHECK (weight >= 0.0 AND weight <= 1.0),
    CONSTRAINT edges_confidence_range CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0))
);

COMMENT ON COLUMN edges.confidence IS 'Derived: LLM confidence, null for user-created edges.';

-- =============================================================================
-- INBOX_ITEMS TABLE (Section 2.4)
-- =============================================================================

CREATE TABLE inbox_items (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    status inbox_item_status NOT NULL DEFAULT 'pending',
    promoted_to_node_id UUID REFERENCES nodes(id) ON DELETE SET NULL
);

-- =============================================================================
-- INDEXES (Section 2.5)
-- =============================================================================

-- Composite on edges for outgoing traversal
CREATE INDEX idx_edges_source_relation ON edges(source_id, relation_type);

-- Composite on edges for backlink queries
CREATE INDEX idx_edges_target_relation ON edges(target_id, relation_type);

-- GIN on nodes type for type filtering
CREATE INDEX idx_nodes_type ON nodes(type);

-- Owner filtering (required for authorization at query layer)
CREATE INDEX idx_nodes_owner ON nodes(owner_id);

-- Full-text search index on title and summary
CREATE INDEX idx_nodes_search ON nodes USING gin(
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, ''))
);

-- Archived filtering
CREATE INDEX idx_nodes_archived ON nodes(archived_at) WHERE archived_at IS NULL;

-- Inbox status
CREATE INDEX idx_inbox_items_status ON inbox_items(status);

-- =============================================================================
-- EDGE TYPE-PAIR CONSTRAINT TRIGGER (Invariant G-01 - database safety net)
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_edge_type_pair()
RETURNS TRIGGER AS $$
DECLARE
    source_type node_type;
    target_type node_type;
    source_owner UUID;
    target_owner UUID;
    valid BOOLEAN := FALSE;
BEGIN
    -- Fetch source and target node types and owners
    SELECT type, owner_id INTO source_type, source_owner FROM nodes WHERE id = NEW.source_id;
    SELECT type, owner_id INTO target_type, target_owner FROM nodes WHERE id = NEW.target_id;

    IF source_type IS NULL OR target_type IS NULL THEN
        RAISE EXCEPTION 'Source or target node not found';
    END IF;

    -- Invariant G-03: Same-owner edge constraint
    IF source_owner != target_owner THEN
        RAISE EXCEPTION 'Invariant G-03: Edges must connect nodes with the same owner. source_owner=%, target_owner=%', source_owner, target_owner;
    END IF;

    -- Invariant G-01: Edge type-pair constraints
    CASE NEW.relation_type
        WHEN 'parent_child' THEN
            valid := (source_type = 'task' AND target_type = 'task')
                  OR (source_type = 'goal' AND target_type = 'goal');
        WHEN 'belongs_to' THEN
            valid := (source_type = 'goal' AND target_type = 'project')
                  OR (source_type = 'task' AND target_type = 'project');
        WHEN 'goal_tracks_task' THEN
            valid := (source_type = 'goal' AND target_type = 'task');
        WHEN 'goal_tracks_kb' THEN
            valid := (source_type = 'goal' AND target_type = 'kb_entry');
        WHEN 'blocked_by' THEN
            valid := (source_type = 'task' AND target_type = 'task')
                  OR (source_type = 'task' AND target_type = 'goal');
        WHEN 'journal_reflects_on' THEN
            valid := (source_type = 'journal_entry');
        WHEN 'derived_from_source' THEN
            valid := (target_type = 'source_item')
                  AND source_type IN ('kb_entry', 'task', 'memory');
        WHEN 'source_supports_goal' THEN
            valid := (source_type = 'source_item' AND target_type = 'goal');
        WHEN 'source_quoted_in' THEN
            valid := (source_type = 'source_item' AND target_type = 'kb_entry');
        WHEN 'captured_for' THEN
            valid := (source_type = 'source_item');
        WHEN 'semantic_reference' THEN
            -- Invariant G-02: bounded semantic_reference
            -- Allowed pairs (bidirectional where noted):
            --   kb_entry <-> kb_entry, kb_entry <-> memory, kb_entry <-> source_item
            --   journal_entry -> any
            --   memory <-> memory
            --   goal <-> kb_entry, goal <-> memory
            --   task <-> kb_entry, task <-> memory
            -- Disallowed where a more specific relation exists:
            --   task <-> task (use parent_child or blocked_by)
            --   goal <-> task (use goal_tracks_task)
            --   source_item <-> goal (use source_supports_goal)
            --   source_item <-> kb_entry (use source_quoted_in or derived_from_source)
            valid := FALSE;

            -- journal_entry -> any
            IF source_type = 'journal_entry' THEN
                valid := TRUE;
            -- kb_entry <-> kb_entry
            ELSIF source_type = 'kb_entry' AND target_type = 'kb_entry' THEN
                valid := TRUE;
            -- kb_entry <-> memory
            ELSIF (source_type = 'kb_entry' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'kb_entry') THEN
                valid := TRUE;
            -- kb_entry <-> source_item
            ELSIF (source_type = 'kb_entry' AND target_type = 'source_item')
               OR (source_type = 'source_item' AND target_type = 'kb_entry') THEN
                valid := TRUE;
            -- memory <-> memory
            ELSIF source_type = 'memory' AND target_type = 'memory' THEN
                valid := TRUE;
            -- goal <-> kb_entry
            ELSIF (source_type = 'goal' AND target_type = 'kb_entry')
               OR (source_type = 'kb_entry' AND target_type = 'goal') THEN
                valid := TRUE;
            -- goal <-> memory
            ELSIF (source_type = 'goal' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'goal') THEN
                valid := TRUE;
            -- task <-> kb_entry
            ELSIF (source_type = 'task' AND target_type = 'kb_entry')
               OR (source_type = 'kb_entry' AND target_type = 'task') THEN
                valid := TRUE;
            -- task <-> memory
            ELSIF (source_type = 'task' AND target_type = 'memory')
               OR (source_type = 'memory' AND target_type = 'task') THEN
                valid := TRUE;
            END IF;
        ELSE
            valid := FALSE;
    END CASE;

    IF NOT valid THEN
        RAISE EXCEPTION 'Invariant G-01: Invalid edge type-pair. relation_type=% not allowed for source_type=% -> target_type=%',
            NEW.relation_type, source_type, target_type;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_edge_type_pair
    BEFORE INSERT OR UPDATE ON edges
    FOR EACH ROW
    EXECUTE FUNCTION validate_edge_type_pair();

-- =============================================================================
-- NODE HARD-DELETE CASCADE (Invariant G-04 + B-02)
-- Edges are cascade-deleted via FK ON DELETE CASCADE.
-- This trigger handles flagging temporal records (node_deleted=true)
-- when we add temporal tables in future phases.
-- =============================================================================

-- Placeholder: Temporal flagging will be added as temporal tables are created.
-- Edge cascade is handled by FK ON DELETE CASCADE on edges table.
-- Derived cache purging will be added as derived tables are created.
-- Pipeline job cancellation will be added when pipeline_jobs table is created.
-- Enrichment deletion will be added when node_enrichments table is created.

-- =============================================================================
-- UPDATED_AT TRIGGER (for last-write-wins conflict policy)
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_nodes_updated_at
    BEFORE UPDATE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
