/**
 * Source list view with processing_status + triage_status tabs.
 * Section 6: Source inbox views (All, Raw, Ready, Promoted, Dismissed, Archived).
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { sourcesApi } from '../../api/endpoints';
import type { SourceResponse, ProcessingStatus, TriageStatus } from '../../types';

type ViewFilter = 'all' | 'raw' | 'ready' | 'promoted' | 'dismissed' | 'archived';

const VIEW_TABS: { label: string; value: ViewFilter }[] = [
  { label: 'All', value: 'all' },
  { label: 'Raw', value: 'raw' },
  { label: 'Ready', value: 'ready' },
  { label: 'Promoted', value: 'promoted' },
  { label: 'Dismissed', value: 'dismissed' },
  { label: 'Archived', value: 'archived' },
];

const STATUS_COLORS: Record<string, string> = {
  raw: tokens.colors.textMuted,
  normalized: tokens.colors.accent,
  enriched: tokens.colors.success,
  error: tokens.colors.error,
  unreviewed: tokens.colors.textMuted,
  ready: tokens.colors.accent,
  promoted: tokens.colors.success,
  dismissed: tokens.colors.textMuted,
};

interface SourceListProps {
  selectedId: string | null;
  onSelect: (source: SourceResponse) => void;
  refreshKey: number;
}

export function SourceList({ selectedId, onSelect, refreshKey }: SourceListProps) {
  const [items, setItems] = useState<SourceResponse[]>([]);
  const [viewFilter, setViewFilter] = useState<ViewFilter>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: {
        processing_status?: ProcessingStatus;
        triage_status?: TriageStatus;
        include_archived?: boolean;
      } = {};

      switch (viewFilter) {
        case 'raw':
          params.processing_status = 'raw';
          break;
        case 'ready':
          params.triage_status = 'ready';
          break;
        case 'promoted':
          params.triage_status = 'promoted';
          break;
        case 'dismissed':
          params.triage_status = 'dismissed';
          break;
        case 'archived':
          params.include_archived = true;
          break;
      }

      const res = await sourcesApi.list(params);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [viewFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {VIEW_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setViewFilter(tab.value)}
            style={{
              ...styles.tab,
              color: viewFilter === tab.value ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: viewFilter === tab.value ? tokens.colors.accent : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.list}>
        {loading && <div style={styles.loading}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.empty}>No sources</div>
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
                ...styles.typeBadge,
                color: tokens.colors.accent,
              }}>
                {item.source_type}
              </span>
              <span style={styles.itemTitle}>{item.title}</span>
            </div>
            <div style={styles.itemMeta}>
              <span style={{
                ...styles.statusBadge,
                color: STATUS_COLORS[item.processing_status] || tokens.colors.textMuted,
              }}>
                {item.processing_status}
              </span>
              <span style={{
                ...styles.statusBadge,
                color: STATUS_COLORS[item.triage_status] || tokens.colors.textMuted,
              }}>
                {item.triage_status}
              </span>
              {item.url && <span style={styles.url}>{new URL(item.url).hostname}</span>}
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
  itemTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  typeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    textTransform: 'uppercase' as const,
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
  statusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
  },
  url: {
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
