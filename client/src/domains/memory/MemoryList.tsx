/**
 * Memory list view with memory_type filtering.
 * Section 2.4: memory_nodes (decision, insight, lesson, principle, preference).
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { memoryApi } from '../../api/endpoints';
import type { MemoryResponse, MemoryType } from '../../types';

const TYPE_TABS: { label: string; value: MemoryType | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Decisions', value: 'decision' },
  { label: 'Insights', value: 'insight' },
  { label: 'Lessons', value: 'lesson' },
  { label: 'Principles', value: 'principle' },
  { label: 'Preferences', value: 'preference' },
];

const TYPE_COLORS: Record<MemoryType, string> = {
  decision: tokens.colors.warning,
  insight: tokens.colors.accent,
  lesson: tokens.colors.success,
  principle: tokens.colors.violet,
  preference: tokens.colors.textMuted,
};

interface MemoryListProps {
  selectedId: string | null;
  onSelect: (memory: MemoryResponse) => void;
  refreshKey: number;
}

export function MemoryList({ selectedId, onSelect, refreshKey }: MemoryListProps) {
  const [items, setItems] = useState<MemoryResponse[]>([]);
  const [typeFilter, setTypeFilter] = useState<MemoryType | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { memory_type?: MemoryType } = {};
      if (typeFilter !== 'all') {
        params.memory_type = typeFilter;
      }
      const res = await memoryApi.list(params);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [typeFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {TYPE_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setTypeFilter(tab.value)}
            style={{
              ...styles.tab,
              color: typeFilter === tab.value ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: typeFilter === tab.value ? tokens.colors.accent : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.list}>
        {loading && <div style={styles.loading}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.empty}>No memories</div>
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
                ...styles.typeDot,
                background: TYPE_COLORS[item.memory_type],
              }} />
              <span style={styles.itemTitle}>{item.title}</span>
            </div>
            <div style={styles.itemMeta}>
              <span style={{
                ...styles.typeBadge,
                color: TYPE_COLORS[item.memory_type],
              }}>
                {item.memory_type}
              </span>
              {item.review_at && (
                <span style={styles.reviewDate}>Review: {new Date(item.review_at).toLocaleDateString()}</span>
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
    padding: '8px 8px',
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
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
  typeDot: {
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
  itemMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  typeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
  },
  reviewDate: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.warning,
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
