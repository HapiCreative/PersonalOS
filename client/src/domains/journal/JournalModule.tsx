/**
 * Journal module: combines ListPane + DetailPane for journal entries.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { JournalList } from './JournalList';
import { JournalDetail } from './JournalDetail';
import { JournalCreate } from './JournalCreate';
import { tokens } from '../../styles/tokens';
import type { JournalResponse } from '../../types';

export function JournalModule() {
  const [selectedEntry, setSelectedEntry] = useState<JournalResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedEntry(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Journal">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedEntry(null); }} style={styles.addButton}>
            + New Entry
          </button>
        </div>
        <JournalList
          selectedId={selectedEntry?.node_id ?? null}
          onSelect={(e) => { setSelectedEntry(e); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane>
        {creating ? (
          <JournalCreate onCreated={handleUpdated} onCancel={() => setCreating(false)} />
        ) : selectedEntry ? (
          <JournalDetail entry={selectedEntry} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a journal entry or create a new one</p>
          </div>
        )}
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { padding: '8px 12px', borderBottom: `1px solid ${tokens.colors.border}` },
  addButton: {
    width: '100%',
    padding: '6px 10px',
    borderRadius: tokens.radius,
    border: `1px dashed ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  placeholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: 8,
  },
  placeholderText: {
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
  },
};
