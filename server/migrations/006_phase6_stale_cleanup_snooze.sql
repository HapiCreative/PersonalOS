-- Phase 6: Stale Detection + Cleanup System + DerivedExplanation
-- Section 3.5: snooze_records (Temporal table)
-- Section 4.6: Stale content detection
-- Section 4.11: DerivedExplanation schema
-- Section 5.6: Cleanup system
-- Invariant D-01: Explainability requirement

-- =============================================================================
-- snooze_records: Temporal table for deferred cleanup items
-- Section 3.5 (Table 25)
-- =============================================================================
CREATE TABLE IF NOT EXISTS snooze_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    snoozed_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Temporal layer: no FKs to other temporal tables (Invariant T-01)
    CONSTRAINT snooze_future CHECK (snoozed_until > created_at)
);

COMMENT ON TABLE snooze_records IS 'Temporal: Deferred cleanup items. Section 3.5, Cleanup System (Section 5.6).';
COMMENT ON COLUMN snooze_records.node_id IS 'Snoozed entity (FK → nodes)';
COMMENT ON COLUMN snooze_records.snoozed_until IS 'When to resurface the item in cleanup queues';

CREATE INDEX idx_snooze_records_node ON snooze_records(node_id);
CREATE INDEX idx_snooze_records_until ON snooze_records(snoozed_until);
CREATE INDEX idx_snooze_records_active ON snooze_records(node_id, snoozed_until)
    WHERE snoozed_until > now();
