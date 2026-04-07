-- Personal OS Phase 3: Sources + KB + Memory + Promotion
-- Implements: source_item_nodes, source_fragments, kb_nodes, memory_nodes
-- Invariants: B-01 (promotion contract), G-02 (semantic_reference for source edges)

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Source type (Section 2.4 / Section 6)
CREATE TYPE source_type AS ENUM (
    'article', 'tweet', 'bookmark', 'note', 'podcast', 'video', 'pdf', 'other'
);

-- Source processing status (Section 6: 4-stage capture workflow)
CREATE TYPE processing_status AS ENUM ('raw', 'normalized', 'enriched', 'error');

-- Source triage status (Section 6: human decision on source item)
CREATE TYPE triage_status AS ENUM ('unreviewed', 'ready', 'promoted', 'dismissed');

-- Source permanence (Section 6)
CREATE TYPE permanence AS ENUM ('ephemeral', 'reference', 'canonical');

-- Source fragment type (Section 6)
CREATE TYPE fragment_type AS ENUM (
    'paragraph', 'quote', 'heading', 'list_item', 'code', 'image_ref'
);

-- KB compile status (Section 7: 6-stage compilation pipeline)
-- ingest → parse → compile → review → accept → stale
CREATE TYPE compile_status AS ENUM (
    'ingest', 'parse', 'compile', 'review', 'accept', 'stale'
);

-- KB pipeline stage (Section 7: 5-stage lifecycle)
CREATE TYPE pipeline_stage AS ENUM (
    'draft', 'review', 'accepted', 'published', 'archived'
);

-- Memory type (Section 2.4)
CREATE TYPE memory_type AS ENUM (
    'decision', 'insight', 'lesson', 'principle', 'preference'
);

-- =============================================================================
-- SOURCE_ITEM_NODES COMPANION TABLE (Section 2.4 / Section 6)
-- =============================================================================
-- Source items represent external content captured into the system.
-- They go through a 4-stage pipeline: capture → normalize → enrich → promote.
-- Invariant B-01: Promotion contract governs how sources become knowledge.

CREATE TABLE source_item_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,

    -- Source identification
    source_type source_type NOT NULL DEFAULT 'other',
    url TEXT,
    author TEXT,
    platform TEXT,
    published_at TIMESTAMPTZ,

    -- Capture metadata
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    capture_context TEXT,  -- e.g. "from daily reading", "research for project X"

    -- Content
    raw_content TEXT NOT NULL DEFAULT '',
    canonical_content TEXT,  -- normalized version after processing

    -- Pipeline status
    processing_status processing_status NOT NULL DEFAULT 'raw',
    triage_status triage_status NOT NULL DEFAULT 'unreviewed',
    permanence permanence NOT NULL DEFAULT 'reference',

    -- Deduplication
    checksum TEXT,  -- for exact-match dedup

    -- Media references
    media_refs JSONB DEFAULT '[]'::jsonb,

    -- AI enrichment flat fields (temporary bridge, flagged for migration to node_enrichments in P9)
    -- These are CACHED DERIVED fields (Invariant S-01)
    ai_summary TEXT,
    ai_takeaways JSONB,  -- array of strings
    ai_entities JSONB    -- array of extracted entities
);

COMMENT ON COLUMN source_item_nodes.ai_summary IS 'CACHED DERIVED: AI-generated summary. Temporary bridge field, migrate to node_enrichments in P9. Invariant S-01.';
COMMENT ON COLUMN source_item_nodes.ai_takeaways IS 'CACHED DERIVED: AI-generated takeaways. Temporary bridge field, migrate to node_enrichments in P9. Invariant S-01.';
COMMENT ON COLUMN source_item_nodes.ai_entities IS 'CACHED DERIVED: AI-extracted entities. Temporary bridge field, migrate to node_enrichments in P9. Invariant S-01.';

-- Indexes for source inbox views (Section 6)
CREATE INDEX idx_source_item_nodes_processing ON source_item_nodes(processing_status);
CREATE INDEX idx_source_item_nodes_triage ON source_item_nodes(triage_status);
CREATE INDEX idx_source_item_nodes_type ON source_item_nodes(source_type);
CREATE INDEX idx_source_item_nodes_checksum ON source_item_nodes(checksum) WHERE checksum IS NOT NULL;
CREATE INDEX idx_source_item_nodes_url ON source_item_nodes(url) WHERE url IS NOT NULL;
CREATE INDEX idx_source_item_nodes_captured ON source_item_nodes(captured_at DESC);

-- =============================================================================
-- SOURCE_FRAGMENTS TABLE (Section 6)
-- =============================================================================
-- Fragments are sub-parts of a source item (paragraphs, quotes, etc.)
-- used for fine-grained retrieval and citation.

CREATE TABLE source_fragments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    fragment_text TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,  -- ordering within the source
    fragment_type fragment_type NOT NULL DEFAULT 'paragraph',
    section_ref TEXT,  -- optional section/heading reference
    -- CACHED DERIVED: embedding for semantic search (Invariant S-01)
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN source_fragments.embedding IS 'CACHED DERIVED: Semantic embedding for fragment-level retrieval. Invariant S-01.';

-- Key indexes (Section 2.5)
CREATE INDEX idx_source_fragments_source ON source_fragments(source_node_id);
CREATE INDEX idx_source_fragments_type ON source_fragments(fragment_type);
CREATE INDEX idx_source_fragments_position ON source_fragments(source_node_id, position);

-- =============================================================================
-- KB_NODES COMPANION TABLE (Section 2.4)
-- =============================================================================
-- Knowledge base entries are canonical, curated knowledge articles.
-- They go through a 6-stage compilation pipeline.

CREATE TABLE kb_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    raw_content TEXT,  -- pre-compilation content
    compile_status compile_status NOT NULL DEFAULT 'draft',
    pipeline_stage pipeline_stage NOT NULL DEFAULT 'draft',
    tags TEXT[] DEFAULT '{}',
    compile_version INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_kb_nodes_compile_status ON kb_nodes(compile_status);
CREATE INDEX idx_kb_nodes_pipeline_stage ON kb_nodes(pipeline_stage);

-- =============================================================================
-- MEMORY_NODES COMPANION TABLE (Section 2.4)
-- =============================================================================
-- Memory nodes capture decisions, insights, lessons, principles, and preferences.

CREATE TABLE memory_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    memory_type memory_type NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    context TEXT,  -- situational context for when this memory was formed
    review_at TIMESTAMPTZ,  -- optional scheduled review date
    tags TEXT[] DEFAULT '{}'
);

CREATE INDEX idx_memory_nodes_type ON memory_nodes(memory_type);
CREATE INDEX idx_memory_nodes_review ON memory_nodes(review_at) WHERE review_at IS NOT NULL;

-- =============================================================================
-- VECTOR INDEXES (Section 2.5)
-- =============================================================================
-- IVFFlat indexes for embedding similarity search.
-- These require data to exist before creation in production;
-- for initial setup we create them and they'll be populated as data arrives.

CREATE INDEX idx_nodes_embedding_ivfflat ON nodes
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_source_fragments_embedding_ivfflat ON source_fragments
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- =============================================================================
-- UPDATE NODE HARD-DELETE CASCADE for Phase 3 tables
-- Invariant B-02: Ensure companion tables and fragments are cleaned up
-- (FK ON DELETE CASCADE handles this automatically, but we document it here)
-- =============================================================================

-- Source fragments are cascade-deleted via FK ON DELETE CASCADE on source_node_id.
-- source_item_nodes, kb_nodes, memory_nodes are cascade-deleted via FK ON DELETE CASCADE on node_id.
