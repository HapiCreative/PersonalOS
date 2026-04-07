/**
 * Goal list view with status filtering.
 * Section 2.4: goal_nodes with status lifecycle.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { goalsApi } from '../../api/endpoints';
import { StaleIndicator } from '../../components/common/StaleIndicator';
import type { GoalResponse, GoalStatus } from '../../types';

// Phase 6: Stale threshold for active goals (Section 4.6, Table 31)
const GOAL_STALE_DAYS = 30;

function getGoalDaysStale(goal: GoalResponse): number | null {
  if (goal.status !== 'active') return null;
  const daysSinceUpdate = Math.floor(
    (Date.now() - new Date(goal.updated_at).getTime()) / (1000 * 60 * 60 * 24)
  );
  return daysSinceUpdate >= GOAL_STALE_DAYS ? daysSinceUpdate : null;
}

const STATUS_TABS: { label: string; value: GoalStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Completed', value: 'completed' },
  { label: 'Archived', value: 'archived' },
];

interface GoalListProps {
  selectedId: string | null;
  onSelect: (goal: GoalResponse) => void;
  refreshKey: number;
}

export function GoalList({ selectedId, onSelect, refreshKey }: GoalListProps) {
  const [items, setItems] = useState<GoalResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState<GoalStatus | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { status?: GoalStatus; include_archived?: boolean } = {};
      if (statusFilter !== 'all') {
        params.status = statusFilter;
        if (statusFilter === 'archived') {
          params.include_archived = true;
        }
      }
      const res = await goalsApi.list(params);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            style={{
              ...styles.tab,
              color: statusFilter === tab.value ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: statusFilter === tab.value ? tokens.colors.accent : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.list}>
        {loading && <div style={styles.loading}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.empty}>No goals</div>
        )}
        {items.map((item) => (
          <button
            key={item.node_id}
            onClick={() => onSelect(item)}
            style={{
              ...styles.item,
              background: selectedId === item.node_id ? `${tokens.colors.accent}15` : 'transparent',
              borderLeftColor: selectedId === item.node_id ? tokens.colors.accent : 'transparent',
            }}
          >
            <div style={styles.itemTop}>
              <span style={styles.itemTitle}>{item.title}</span>
              {/* Phase 6: Stale indicator */}
              {(() => {
                const daysStale = getGoalDaysStale(item);
                return daysStale ? <StaleIndicator daysStale={daysStale} prompt="Pause or adjust?" /> : null;
              })()}
            </div>
            <div style={styles.itemMeta}>
              <span style={{
                ...styles.statusBadge,
                color: item.status === 'active' ? tokens.colors.accent
                  : item.status === 'completed' ? tokens.colors.success
                  : tokens.colors.textMuted,
              }}>
                {item.status}
              </span>
              <span style={styles.progress}>
                {Math.round(item.progress * 100)}%
              </span>
              {item.timeframe_label && (
                <span style={styles.timeframe}>{item.timeframe_label}</span>
              )}
            </div>
            {/* Progress bar */}
            <div style={styles.progressBarContainer}>
              <div style={{
                ...styles.progressBarFill,
                width: `${Math.round(item.progress * 100)}%`,
                background: item.status === 'completed' ? tokens.colors.success : tokens.colors.accent,
              }} />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  tabs: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
    overflow: 'auto',
  },
  tab: {
    padding: '8px 10px',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
    whiteSpace: 'nowrap' as const,
  },
  list: { flex: 1, overflowY: 'auto' },
  item: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    padding: '10px 16px',
    borderLeft: '2px solid transparent',
    borderBottom: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
    textAlign: 'left' as const,
    gap: 4,
    transition: 'background 0.1s',
    background: 'none',
  },
  itemTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    flex: 1,
  },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  statusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
  },
  progress: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  timeframe: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  progressBarContainer: {
    width: '100%',
    height: 3,
    background: tokens.colors.border,
    borderRadius: 2,
    marginTop: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 0.3s ease',
  },
  loading: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
  },
  empty: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
  },
};
