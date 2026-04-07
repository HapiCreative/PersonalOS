/**
 * Task list view with status/priority filtering.
 * Section 2.4: task_nodes with status lifecycle.
 * Invariant B-03: State machine transitions visible in UI.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { tasksApi } from '../../api/endpoints';
import type { TaskResponse, TaskStatus, TaskPriority } from '../../types';

const STATUS_TABS: { label: string; value: TaskStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Todo', value: 'todo' },
  { label: 'In Progress', value: 'in_progress' },
  { label: 'Done', value: 'done' },
  { label: 'Cancelled', value: 'cancelled' },
];

const PRIORITY_COLORS: Record<TaskPriority, string> = {
  urgent: tokens.colors.error,
  high: tokens.colors.warning,
  medium: tokens.colors.accent,
  low: tokens.colors.textMuted,
};

interface TaskListProps {
  selectedId: string | null;
  onSelect: (task: TaskResponse) => void;
  refreshKey: number;
}

export function TaskList({ selectedId, onSelect, refreshKey }: TaskListProps) {
  const [items, setItems] = useState<TaskResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { status?: TaskStatus; include_archived?: boolean } = {};
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const res = await tasksApi.list(params);
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
          <div style={styles.empty}>No tasks</div>
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
              <span style={{
                ...styles.priorityDot,
                background: PRIORITY_COLORS[item.priority],
              }} />
              <span style={styles.itemTitle}>{item.title}</span>
              {item.is_recurring && <span style={styles.recurringBadge}>↻</span>}
            </div>
            <div style={styles.itemMeta}>
              <span style={styles.statusBadge}>{item.status.replace('_', ' ')}</span>
              {item.due_date && (
                <span style={styles.date}>{item.due_date}</span>
              )}
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
  priorityDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    flexShrink: 0,
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
  recurringBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.accent,
    flexShrink: 0,
  },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  statusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    textTransform: 'capitalize' as const,
  },
  date: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
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
