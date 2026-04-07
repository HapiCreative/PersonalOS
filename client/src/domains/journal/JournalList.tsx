/**
 * Journal list view sorted by date with mood filter.
 * Section 2.4: journal_nodes with mood ENUM.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { journalApi } from '../../api/endpoints';
import type { JournalResponse, Mood } from '../../types';

const MOOD_EMOJI: Record<Mood, string> = {
  great: '✨',
  good: '🙂',
  neutral: '😐',
  low: '😔',
  bad: '😞',
};

const MOOD_TABS: { label: string; value: Mood | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: '✨', value: 'great' },
  { label: '🙂', value: 'good' },
  { label: '😐', value: 'neutral' },
  { label: '😔', value: 'low' },
  { label: '😞', value: 'bad' },
];

interface JournalListProps {
  selectedId: string | null;
  onSelect: (entry: JournalResponse) => void;
  refreshKey: number;
}

export function JournalList({ selectedId, onSelect, refreshKey }: JournalListProps) {
  const [items, setItems] = useState<JournalResponse[]>([]);
  const [moodFilter, setMoodFilter] = useState<Mood | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { mood?: Mood } = {};
      if (moodFilter !== 'all') params.mood = moodFilter;
      const res = await journalApi.list(params);
      setItems(res.items);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [moodFilter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {MOOD_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setMoodFilter(tab.value)}
            style={{
              ...styles.tab,
              color: moodFilter === tab.value ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: moodFilter === tab.value ? tokens.colors.accent : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.list}>
        {loading && <div style={styles.loading}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.empty}>No journal entries</div>
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
              {item.mood && <span style={styles.moodBadge}>{MOOD_EMOJI[item.mood]}</span>}
            </div>
            <div style={styles.itemMeta}>
              <span style={styles.date}>{item.entry_date}</span>
              <span style={styles.wordCount}>{item.word_count} words</span>
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
    fontSize: 14,
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
  moodBadge: { fontSize: 14 },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  date: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  wordCount: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  tags: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.accent },
  loading: { padding: 16, color: tokens.colors.textMuted, fontSize: 13, textAlign: 'center' as const },
  empty: { padding: 16, color: tokens.colors.textMuted, fontSize: 13, textAlign: 'center' as const },
};
