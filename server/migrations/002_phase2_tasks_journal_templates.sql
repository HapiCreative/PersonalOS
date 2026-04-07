-- Personal OS Phase 2: Tasks + Journal + Execution Events + Templates
-- Implements: task_nodes, journal_nodes, templates, task_execution_events
-- Invariants: S-02, S-03, S-04, T-01, T-02, T-04, B-03

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Task status (Section 2.4 - task_nodes)
-- Status rules: todo → in_progress → done (non-recurring only)
--               todo → cancelled, in_progress → cancelled
-- Invariant S-02: recurring + done = invalid
CREATE TYPE task_status AS ENUM ('todo', 'in_progress', 'done', 'cancelled');

-- Task priority (Section 2.4 - task_nodes)
CREATE TYPE task_priority AS ENUM ('low', 'medium', 'high', 'urgent');

-- Mood (Section 2.4 - journal_nodes)
-- v6 change: mood changed from free TEXT to ENUM for analytics queryability
CREATE TYPE mood AS ENUM ('great', 'good', 'neutral', 'low', 'bad');

-- Task execution event type (Section 3.7)
CREATE TYPE task_execution_event_type AS ENUM ('completed', 'skipped', 'deferred');

-- Template target type (Section 2.4 - templates)
CREATE TYPE template_target_type AS ENUM ('goal', 'task', 'journal_entry');

-- =============================================================================
-- TASK_NODES COMPANION TABLE (Section 2.4)
-- =============================================================================

CREATE TABLE task_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    status task_status NOT NULL DEFAULT 'todo',
    priority task_priority NOT NULL DEFAULT 'medium',
    due_date DATE,
    recurrence TEXT,  -- cron expression for recurring tasks
    -- Invariant S-01: CACHED DERIVED - convenience flag derived from recurrence IS NOT NULL
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,

    -- Invariant S-02: Recurring task + done = invalid (database safety net)
    CONSTRAINT task_recurring_done_invalid CHECK (
        NOT (recurrence IS NOT NULL AND status = 'done')
    )
);

COMMENT ON COLUMN task_nodes.is_recurring IS 'CACHED DERIVED: Convenience flag, derived from recurrence IS NOT NULL. Invariant S-01.';

-- Per-domain indexes (Section 2.5)
CREATE INDEX idx_task_nodes_status_due ON task_nodes(status, due_date);
CREATE INDEX idx_task_nodes_priority ON task_nodes(priority);

-- =============================================================================
-- JOURNAL_NODES COMPANION TABLE (Section 2.4)
-- =============================================================================

CREATE TABLE journal_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    content TEXT NOT NULL DEFAULT '',
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    mood mood,
    tags TEXT[] DEFAULT '{}',
    -- Invariant S-01: CACHED DERIVED - computed from content length
    word_count INTEGER NOT NULL DEFAULT 0
);

COMMENT ON COLUMN journal_nodes.word_count IS 'CACHED DERIVED: Computed from content length. Invariant S-01.';

CREATE INDEX idx_journal_nodes_entry_date ON journal_nodes(entry_date DESC);
CREATE INDEX idx_journal_nodes_mood ON journal_nodes(mood);

-- =============================================================================
-- TEMPLATES TABLE (Section 2.4 - System Configuration)
-- =============================================================================

CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_type template_target_type NOT NULL,
    structure JSONB NOT NULL DEFAULT '{}',
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_templates_owner ON templates(owner_id);
CREATE INDEX idx_templates_target_type ON templates(target_type);

-- Updated_at trigger for templates
CREATE TRIGGER trg_templates_updated_at
    BEFORE UPDATE ON templates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- TASK_EXECUTION_EVENTS TEMPORAL TABLE (Section 3.7)
-- =============================================================================
-- Invariant T-01: No temporal-to-temporal FKs (references task via node_id only)
-- Invariant T-02: Append-only (no UPDATE trigger enforced at application layer)
-- Invariant T-04: Ownership alignment (user_id must match task node's owner_id)
-- Invariant S-04: Unique constraint on task_id + expected_for_date for terminal events

CREATE TABLE task_execution_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type task_execution_event_type NOT NULL,
    expected_for_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Invariant B-02: Flag for when referenced node is hard-deleted
    -- Invariant T-03: Temporal records are never deleted, only flagged
    node_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- Invariant S-04: At most one terminal execution event per task per expected_for_date
CREATE UNIQUE INDEX idx_task_execution_events_unique
    ON task_execution_events(task_id, expected_for_date)
    WHERE node_deleted = FALSE;

CREATE INDEX idx_task_execution_events_task ON task_execution_events(task_id);
CREATE INDEX idx_task_execution_events_date ON task_execution_events(expected_for_date);
CREATE INDEX idx_task_execution_events_user ON task_execution_events(user_id);

-- =============================================================================
-- INVARIANT T-02: Append-only enforcement for task_execution_events
-- Updates are not permitted; corrections require explicit override semantics
-- =============================================================================

CREATE OR REPLACE FUNCTION prevent_execution_event_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Allow only node_deleted flag updates (for hard-delete cascade)
    IF OLD.node_deleted = FALSE AND NEW.node_deleted = TRUE
       AND OLD.task_id = NEW.task_id
       AND OLD.user_id = NEW.user_id
       AND OLD.event_type = NEW.event_type
       AND OLD.expected_for_date = NEW.expected_for_date
       AND OLD.notes IS NOT DISTINCT FROM NEW.notes
       AND OLD.created_at = NEW.created_at
    THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Invariant T-02: task_execution_events are append-only. Updates not permitted except for node_deleted flagging.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_execution_event_update
    BEFORE UPDATE ON task_execution_events
    FOR EACH ROW
    EXECUTE FUNCTION prevent_execution_event_update();

-- =============================================================================
-- INVARIANT T-04: Ownership alignment enforcement
-- task_execution_events.user_id must match the owner_id of the referenced task node
-- =============================================================================

CREATE OR REPLACE FUNCTION validate_execution_event_ownership()
RETURNS TRIGGER AS $$
DECLARE
    task_owner UUID;
BEGIN
    SELECT owner_id INTO task_owner FROM nodes WHERE id = NEW.task_id;

    IF task_owner IS NULL THEN
        RAISE EXCEPTION 'Task node not found: %', NEW.task_id;
    END IF;

    IF task_owner != NEW.user_id THEN
        RAISE EXCEPTION 'Invariant T-04: Ownership alignment violation. Event user_id (%) does not match task owner_id (%)',
            NEW.user_id, task_owner;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_execution_event_ownership
    BEFORE INSERT ON task_execution_events
    FOR EACH ROW
    EXECUTE FUNCTION validate_execution_event_ownership();

-- =============================================================================
-- UPDATE NODE HARD-DELETE CASCADE for Phase 2 temporal tables
-- Invariant B-02: Flag temporal records when referenced node is hard-deleted
-- Invariant T-03: Temporal records are never deleted, only flagged
-- =============================================================================

CREATE OR REPLACE FUNCTION flag_temporal_on_node_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- Flag task_execution_events as node_deleted
    UPDATE task_execution_events
    SET node_deleted = TRUE
    WHERE task_id = OLD.id AND node_deleted = FALSE;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_flag_temporal_on_node_delete
    BEFORE DELETE ON nodes
    FOR EACH ROW
    EXECUTE FUNCTION flag_temporal_on_node_delete();
