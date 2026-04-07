/**
 * Sources module: combines ListPane + DetailPane for the sources domain.
 * Section 6: Source triage / promotion workflow.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { SourceList } from './SourceList';
import { SourceDetail } from './SourceDetail';
import { SourceCreate } from './SourceCreate';
import { tokens } from '../../styles/tokens';
import type { SourceResponse } from '../../types';

export function SourcesModule() {
  const [selectedSource, setSelectedSource] = useState<SourceResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedSource(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Sources">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedSource(null); }} style={styles.addButton}>
            + Capture Source
          </button>
        </div>
        <SourceList
          selectedId={selectedSource?.node_id ?? null}
          onSelect={(s) => { setSelectedSource(s); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane nodeId={selectedSource?.node_id}>
        {creating ? (
          <SourceCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedSource ? (
          <SourceDetail source={selectedSource} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a source or capture a new one</p>
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
