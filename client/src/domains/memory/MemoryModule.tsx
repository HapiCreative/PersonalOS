/**
 * Memory module: combines ListPane + DetailPane for the memory domain.
 * Section 2.4: memory_nodes.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { MemoryList } from './MemoryList';
import { MemoryDetail } from './MemoryDetail';
import { MemoryCreate } from './MemoryCreate';
import { tokens } from '../../styles/tokens';
import type { MemoryResponse } from '../../types';

export function MemoryModule() {
  const [selectedMemory, setSelectedMemory] = useState<MemoryResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedMemory(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Memory">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedMemory(null); }} style={styles.addButton}>
            + New Memory
          </button>
        </div>
        <MemoryList
          selectedId={selectedMemory?.node_id ?? null}
          onSelect={(m) => { setSelectedMemory(m); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane nodeId={selectedMemory?.node_id}>
        {creating ? (
          <MemoryCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedMemory ? (
          <MemoryDetail memory={selectedMemory} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a memory or create a new one</p>
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
