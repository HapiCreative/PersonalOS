/**
 * KB module: combines ListPane + DetailPane for the knowledge base domain.
 * Section 7: KB compilation pipeline UI.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { KBList } from './KBList';
import { KBDetail } from './KBDetail';
import { KBCreate } from './KBCreate';
import { tokens } from '../../styles/tokens';
import type { KBResponse } from '../../types';

export function KBModule() {
  const [selectedKB, setSelectedKB] = useState<KBResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedKB(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Knowledge Base">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedKB(null); }} style={styles.addButton}>
            + New Entry
          </button>
        </div>
        <KBList
          selectedId={selectedKB?.node_id ?? null}
          onSelect={(k) => { setSelectedKB(k); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane>
        {creating ? (
          <KBCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedKB ? (
          <KBDetail kb={selectedKB} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a KB entry or create a new one</p>
          </div>
        )}
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    padding: '8px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
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
