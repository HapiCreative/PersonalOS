-- Phase 8: Projects + Weekly/Monthly Reviews
-- Tables: project_nodes, weekly_snapshots, monthly_snapshots
-- Invariant G-05: belongs_to edges restricted to goal→project, task→project

-- =============================================================================
-- 1. project_nodes companion table (Section 2.4, TABLE 19)
-- Lightweight containers grouping goals/tasks via belongs_to edges.
-- =============================================================================

CREATE TYPE project_status AS ENUM ('active', 'completed', 'archived');

CREATE TABLE IF NOT EXISTS project_nodes (
    node_id UUID PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    status project_status NOT NULL DEFAULT 'active',
    description TEXT NULL,
    tags TEXT[] DEFAULT '{}'
);

CREATE INDEX idx_project_nodes_status ON project_nodes(status);

COMMENT ON TABLE project_nodes IS 'Section 2.4: project_nodes companion table. Lightweight containers grouping goals via belongs_to edges.';

-- =============================================================================
-- 2. weekly_snapshots temporal table (Section 3.2, TABLE 22)
-- Invariant T-01: No temporal-to-temporal FKs.
-- Invariant T-04: Ownership alignment via user_id.
-- =============================================================================

CREATE TABLE IF NOT EXISTS weekly_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    focus_areas TEXT[] NOT NULL DEFAULT '{}',
    priority_task_ids UUID[] NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_weekly_snapshots_user_week ON weekly_snapshots(user_id, week_start_date);
CREATE INDEX idx_weekly_snapshots_user ON weekly_snapshots(user_id);
CREATE INDEX idx_weekly_snapshots_week ON weekly_snapshots(week_start_date);

COMMENT ON TABLE weekly_snapshots IS 'Section 3.2: Weekly review output. Temporal record, append-heavy, not in graph.';

-- =============================================================================
-- 3. monthly_snapshots temporal table (Section 3.3, TABLE 23)
-- Invariant T-01: No temporal-to-temporal FKs.
-- Invariant T-04: Ownership alignment via user_id.
-- =============================================================================

CREATE TABLE IF NOT EXISTS monthly_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    month DATE NOT NULL,
    focus_areas TEXT[] NOT NULL DEFAULT '{}',
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_monthly_snapshots_user_month ON monthly_snapshots(user_id, month);
CREATE INDEX idx_monthly_snapshots_user ON monthly_snapshots(user_id);
CREATE INDEX idx_monthly_snapshots_month ON monthly_snapshots(month);

COMMENT ON TABLE monthly_snapshots IS 'Section 3.3: Monthly review output. Temporal record, append-heavy, not in graph.';

-- =============================================================================
-- 4. G-05 safety net trigger: belongs_to restriction
-- belongs_to edges are restricted to: goal → project and task → project.
-- Application layer is primary enforcement; this is the database safety net.
-- =============================================================================

CREATE OR REPLACE FUNCTION enforce_belongs_to_restriction()
RETURNS TRIGGER AS $$
DECLARE
    source_type TEXT;
    target_type TEXT;
BEGIN
    IF NEW.relation_type = 'belongs_to' THEN
        SELECT type INTO source_type FROM nodes WHERE id = NEW.source_id;
        SELECT type INTO target_type FROM nodes WHERE id = NEW.target_id;

        IF NOT (
            (source_type = 'goal' AND target_type = 'project') OR
            (source_type = 'task' AND target_type = 'project')
        ) THEN
            RAISE EXCEPTION 'Invariant G-05: belongs_to edges restricted to goal→project, task→project. Got %→%', source_type, target_type;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_belongs_to ON edges;
CREATE TRIGGER trg_enforce_belongs_to
    BEFORE INSERT OR UPDATE ON edges
    FOR EACH ROW
    EXECUTE FUNCTION enforce_belongs_to_restriction();
