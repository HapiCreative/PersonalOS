/**
 * KB list view with compile_status filtering.
 * Section 7: KB compilation pipeline (6-stage).
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { kbApi } from '../../api/endpoints';
import type { KBResponse, CompileStatus } from '../../types';

const STATUS_TABS: { label: string; value: CompileStatus | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Ingest', value: 'ingest' },
  { label: 'Review', value: 'review' },
  { label: 'Accepted', value: 'accept' },
  { label: 'Stale', value: 'stale' },
];

const STATUS_COLORS: Record<CompileStatus, string> = {
  ingest: tokens.colors.textMuted,
  parse: tokens.colors.textMuted,
  compile: tokens.colors.accent,
  review: tokens.colors.warning,
  accept: tokens.colors.success,
  stale: tokens.colors.error,
};

interface KBListProps {
  selectedId: string | null;
  onSelect: (kb: KBResponse) => void;
  refreshKey: number;
}

export function KBList({ selectedId, onSelect, refreshKey }: KBListProps) {
  const [items, setItems] = useState<KBResponse[]>([]);
  const [statusFilter, setStatusFilter] = useState<CompileStatus | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { compile_status?: CompileStatus } = {};
      if (statusFilter !== 'all') {
        params.compile_status = statusFilter;
      }
      const res = await kbApi.list(params);
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
          <div style={styles.empty}>No KB entries</div>
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
            </div>
            <div style={styles.itemMeta}>
              <span style={{
                ...styles.statusBadge,
                color: STATUS_COLORS[item.compile_status],
              }}>
                {item.compile_status}
              </span>
              <span style={styles.version}>v{item.compile_version}</span>
              {item.tags.length > 0 && (
                <span style={styles.tags}>{item.tags.slice(0, 2).join(', ')}</span>
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
  itemTop: { display: 'flex', alignItems: 'center', gap: 8 },
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
  version: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  tags: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
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
