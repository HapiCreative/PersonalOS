/**
 * Inbox list view with status filtering.
 * Section 2.4: inbox_items with status lifecycle.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { inboxApi } from '../../api/endpoints';
import type { InboxItemResponse, InboxItemStatus } from '../../types';

const STATUS_TABS: { label: string; value: InboxItemStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Pending', value: 'pending' },
  { label: 'Promoted', value: 'promoted' },
  { label: 'Dismissed', value: 'dismissed' },
  { label: 'Archived', value: 'archived' },
];

interface InboxListProps {
  selectedId: string | null;
  onSelect: (item: InboxItemResponse) => void;
  refreshKey: number;
}

export function InboxList({ selectedId, onSelect, refreshKey }: InboxListProps) {
  const [items, setItems] = useState<InboxItemResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState<InboxItemStatus | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { status?: InboxItemStatus; include_archived?: boolean } = {};
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      if (statusFilter === 'archived') {
        params.include_archived = true;
      }
      const res = await inboxApi.list(params);
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
          <div style={styles.empty}>No inbox items</div>
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
            <span style={styles.itemTitle}>{item.title}</span>
            <div style={styles.itemMeta}>
              <span style={styles.statusBadge}>{item.status}</span>
              <span style={styles.date}>
                {new Date(item.created_at).toLocaleDateString()}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
  },
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
  list: {
    flex: 1,
    overflowY: 'auto',
  },
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
  },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  itemMeta: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  statusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
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
