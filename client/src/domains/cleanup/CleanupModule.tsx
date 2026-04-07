/**
 * Cleanup Module: Card-based review queue (Section 5.6).
 *
 * Features:
 * - Cleanup session UI: card-based review queue
 * - Snooze date picker
 * - Batch action toolbar
 * - Stale indicators on list items
 * - DerivedExplanation display component
 *
 * Section 5.6:
 * - Review queues: Stale Tasks, Inactive Goals, Unprocessed Sources, Low-signal KB
 * - 5-10 items per session, <90 second sessions
 * - One-click actions: Archive, Snooze (with date), Keep
 *
 * Invariant D-01: All stale flags use DerivedExplanation.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { cleanupApi } from '../../api/endpoints';
import { DerivedExplanationDisplay } from '../../components/derived/DerivedExplanationDisplay';
import type { CleanupQueueResponse, StaleItemResponse, CleanupAction } from '../../types';

const CATEGORY_LABELS: Record<string, string> = {
  task_todo: 'Stale Tasks (Todo)',
  task_in_progress: 'Stale Tasks (In Progress)',
  goal_active: 'Inactive Goals',
  kb_accepted: 'Low-Signal KB',
  inbox_pending: 'Unprocessed Inbox',
  source_raw: 'Unprocessed Sources',
};

const CATEGORY_COLORS: Record<string, string> = {
  task_todo: tokens.colors.warning,
  task_in_progress: tokens.colors.error,
  goal_active: tokens.colors.violet,
  kb_accepted: tokens.colors.warning,
  inbox_pending: tokens.colors.accent,
  source_raw: tokens.colors.textMuted,
};

interface CleanupModuleProps {
  onNavigate?: (module: string) => void;
}

export function CleanupModule({ onNavigate }: CleanupModuleProps) {
  const [queue, setQueue] = useState<CleanupQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [snoozeNodeId, setSnoozeNodeId] = useState<string | null>(null);
  const [snoozeDate, setSnoozeDate] = useState('');

  const fetchQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await cleanupApi.getQueue({
        category: categoryFilter || undefined,
        limit: 10,
      });
      setQueue(result);
      setSelectedIds(new Set());
    } catch (e: any) {
      setError(e.message || 'Failed to load cleanup queue');
    } finally {
      setLoading(false);
    }
  }, [categoryFilter]);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  const handleAction = async (action: CleanupAction, nodeIds?: string[], snoozedUntil?: string) => {
    const ids = nodeIds || Array.from(selectedIds);
    if (ids.length === 0) return;

    setActionLoading(true);
    try {
      await cleanupApi.executeAction({
        action,
        node_ids: ids,
        snoozed_until: snoozedUntil,
      });
      await fetchQueue();
    } catch (e: any) {
      setError(e.message || `Failed to ${action}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSnoozeConfirm = async () => {
    if (!snoozeNodeId || !snoozeDate) return;
    await handleAction('snooze', [snoozeNodeId], new Date(snoozeDate).toISOString());
    setSnoozeNodeId(null);
    setSnoozeDate('');
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (!queue) return;
    if (selectedIds.size === queue.items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(queue.items.map((i) => i.node_id)));
    }
  };

  if (loading) {
    return (
      <div style={styles.fullWidth}>
        <div style={styles.loadingState}>Loading cleanup queue...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.fullWidth}>
        <div style={styles.errorState}>
          <p>{error}</p>
          <button onClick={fetchQueue} style={styles.retryButton}>Retry</button>
        </div>
      </div>
    );
  }

  if (!queue) return null;

  const categories = Object.keys(queue.categories);

  return (
    <div style={styles.fullWidth}>
      <div style={styles.container}>
        {/* Header */}
        <div style={styles.header}>
          <h1 style={styles.heading}>Cleanup</h1>
          <div style={styles.stats}>
            <span style={styles.statChip}>{queue.total_stale} stale</span>
            {queue.total_snoozed > 0 && (
              <span style={styles.statChipMuted}>{queue.total_snoozed} snoozed</span>
            )}
          </div>
        </div>

        {/* Category filter tabs */}
        <div style={styles.filterRow}>
          <button
            onClick={() => setCategoryFilter(null)}
            style={{
              ...styles.filterChip,
              ...(categoryFilter === null ? styles.filterChipActive : {}),
            }}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              style={{
                ...styles.filterChip,
                ...(categoryFilter === cat ? styles.filterChipActive : {}),
              }}
            >
              {CATEGORY_LABELS[cat] || cat}
              <span style={styles.filterCount}>
                {queue.categories[cat]?.length || 0}
              </span>
            </button>
          ))}
        </div>

        {/* Batch action toolbar */}
        {selectedIds.size > 0 && (
          <div style={styles.batchToolbar}>
            <span style={styles.batchLabel}>
              {selectedIds.size} selected
            </span>
            <button
              onClick={() => handleAction('archive')}
              disabled={actionLoading}
              style={styles.batchButton}
            >
              Archive
            </button>
            <button
              onClick={() => handleAction('keep')}
              disabled={actionLoading}
              style={styles.batchButtonKeep}
            >
              Keep
            </button>
          </div>
        )}

        {/* Items */}
        {queue.items.length === 0 ? (
          <div style={styles.emptyState}>
            <p style={styles.emptyTitle}>All clear!</p>
            <p style={styles.emptySubtitle}>No stale items need attention right now.</p>
          </div>
        ) : (
          <div style={styles.cardList}>
            {/* Select all */}
            <button onClick={selectAll} style={styles.selectAllButton}>
              {selectedIds.size === queue.items.length ? 'Deselect all' : 'Select all'}
            </button>

            {queue.items.map((item) => (
              <CleanupCard
                key={item.node_id}
                item={item}
                selected={selectedIds.has(item.node_id)}
                onToggle={() => toggleSelect(item.node_id)}
                onArchive={() => handleAction('archive', [item.node_id])}
                onKeep={() => handleAction('keep', [item.node_id])}
                onSnooze={() => {
                  setSnoozeNodeId(item.node_id);
                  setSnoozeDate('');
                }}
                actionLoading={actionLoading}
              />
            ))}
          </div>
        )}

        {/* Snooze date picker modal */}
        {snoozeNodeId && (
          <div style={styles.snoozeOverlay}>
            <div style={styles.snoozeModal}>
              <h3 style={styles.snoozeTitle}>Snooze until</h3>
              <input
                type="date"
                value={snoozeDate}
                onChange={(e) => setSnoozeDate(e.target.value)}
                style={styles.snoozeDateInput}
                min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
              />
              <div style={styles.snoozePresets}>
                {[
                  { label: '1 week', days: 7 },
                  { label: '2 weeks', days: 14 },
                  { label: '1 month', days: 30 },
                ].map(({ label, days }) => (
                  <button
                    key={label}
                    onClick={() => {
                      const d = new Date();
                      d.setDate(d.getDate() + days);
                      setSnoozeDate(d.toISOString().split('T')[0]);
                    }}
                    style={styles.snoozePresetButton}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <div style={styles.snoozeActions}>
                <button
                  onClick={() => setSnoozeNodeId(null)}
                  style={styles.snoozeCancelButton}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSnoozeConfirm}
                  disabled={!snoozeDate || actionLoading}
                  style={{
                    ...styles.snoozeConfirmButton,
                    opacity: !snoozeDate ? 0.5 : 1,
                  }}
                >
                  Snooze
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CleanupCard({
  item,
  selected,
  onToggle,
  onArchive,
  onKeep,
  onSnooze,
  actionLoading,
}: {
  item: StaleItemResponse;
  selected: boolean;
  onToggle: () => void;
  onArchive: () => void;
  onKeep: () => void;
  onSnooze: () => void;
  actionLoading: boolean;
}) {
  const categoryColor = CATEGORY_COLORS[item.stale_category] || tokens.colors.warning;

  return (
    <div
      style={{
        ...styles.card,
        borderLeftColor: categoryColor,
        background: selected ? `${tokens.colors.accent}08` : tokens.colors.surface,
      }}
    >
      <div style={styles.cardTop}>
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          style={styles.checkbox}
        />
        <div style={styles.cardContent}>
          <div style={styles.cardHeader}>
            <span style={styles.cardTitle}>{item.title}</span>
            <span
              style={{
                ...styles.staleBadge,
                color: categoryColor,
                borderColor: `${categoryColor}60`,
              }}
            >
              {item.days_stale}d stale
            </span>
          </div>
          <span style={styles.cardCategory}>
            {CATEGORY_LABELS[item.stale_category] || item.stale_category}
          </span>

          {/* Invariant D-01: DerivedExplanation display */}
          <DerivedExplanationDisplay explanation={item.explanation} />
        </div>
      </div>

      {/* Action buttons */}
      <div style={styles.cardActions}>
        <button
          onClick={onArchive}
          disabled={actionLoading}
          style={styles.actionButton}
          title="Archive"
        >
          Archive
        </button>
        <button
          onClick={onSnooze}
          disabled={actionLoading}
          style={styles.actionButton}
          title="Snooze"
        >
          Snooze
        </button>
        <button
          onClick={onKeep}
          disabled={actionLoading}
          style={styles.actionButtonKeep}
          title="Keep (reset stale clock)"
        >
          Keep
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  fullWidth: {
    flex: 1,
    height: '100%',
    overflowY: 'auto',
    background: tokens.colors.background,
  },
  container: {
    maxWidth: 720,
    margin: '0 auto',
    padding: '24px 20px',
  },
  loadingState: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
  },
  errorState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    gap: 12,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.error,
  },
  retryButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    cursor: 'pointer',
    background: 'none',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 16,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
    margin: 0,
  },
  stats: {
    display: 'flex',
    gap: 8,
  },
  statChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.warning,
    padding: '2px 8px',
    border: `1px solid ${tokens.colors.warning}40`,
    borderRadius: tokens.radius,
  },
  statChipMuted: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.textMuted,
    padding: '2px 8px',
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  filterRow: {
    display: 'flex',
    gap: 6,
    marginBottom: 16,
    flexWrap: 'wrap' as const,
  },
  filterChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    background: 'none',
    cursor: 'pointer',
  },
  filterChipActive: {
    color: tokens.colors.accent,
    borderColor: tokens.colors.accent,
    background: `${tokens.colors.accent}10`,
  },
  filterCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: 'inherit',
    opacity: 0.7,
  },
  batchToolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 12px',
    marginBottom: 12,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  batchLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.accent,
    flex: 1,
  },
  batchButton: {
    padding: '4px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.error}60`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.error,
    background: 'none',
    cursor: 'pointer',
  },
  batchButtonKeep: {
    padding: '4px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.success}60`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.success,
    background: 'none',
    cursor: 'pointer',
  },
  emptyState: {
    textAlign: 'center' as const,
    padding: '48px 0',
  },
  emptyTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 18,
    fontWeight: 600,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  emptySubtitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
  },
  cardList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  selectAllButton: {
    alignSelf: 'flex-start',
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    background: 'none',
    cursor: 'pointer',
    marginBottom: 4,
  },
  card: {
    display: 'flex',
    flexDirection: 'column',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    borderLeft: '3px solid',
    overflow: 'hidden',
  },
  cardTop: {
    display: 'flex',
    gap: 10,
    padding: '10px 12px',
  },
  checkbox: {
    width: 16,
    height: 16,
    flexShrink: 0,
    marginTop: 2,
    accentColor: tokens.colors.accent,
  },
  cardContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  cardTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    color: tokens.colors.text,
    flex: 1,
  },
  staleBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    padding: '1px 6px',
    border: '1px solid',
    borderRadius: tokens.radius,
    flexShrink: 0,
  },
  cardCategory: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  cardActions: {
    display: 'flex',
    gap: 0,
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  actionButton: {
    flex: 1,
    padding: '6px 0',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    background: 'none',
    border: 'none',
    borderRight: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
  },
  actionButtonKeep: {
    flex: 1,
    padding: '6px 0',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.success,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
  },
  // Snooze modal
  snoozeOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    zIndex: 100,
  },
  snoozeModal: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: 20,
    width: 300,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  snoozeTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 16,
    color: tokens.colors.text,
    margin: 0,
  },
  snoozeDateInput: {
    width: '100%',
    padding: '8px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.text,
    background: tokens.colors.background,
  },
  snoozePresets: {
    display: 'flex',
    gap: 6,
  },
  snoozePresetButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    background: 'none',
    cursor: 'pointer',
  },
  snoozeActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 4,
  },
  snoozeCancelButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    background: 'none',
    cursor: 'pointer',
  },
  snoozeConfirmButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.accent}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    cursor: 'pointer',
  },
};
