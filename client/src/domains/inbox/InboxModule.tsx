/**
 * Inbox module: combines ListPane + DetailPane for the inbox domain.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { InboxList } from './InboxList';
import { InboxDetail } from './InboxDetail';
import { tokens } from '../../styles/tokens';
import type { InboxItemResponse } from '../../types';

export function InboxModule() {
  const [selectedItem, setSelectedItem] = useState<InboxItemResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedItem(null);
  }, []);

  return (
    <>
      <ListPane title="Inbox">
        <InboxList
          selectedId={selectedItem?.node_id ?? null}
          onSelect={setSelectedItem}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane>
        {selectedItem ? (
          <InboxDetail item={selectedItem} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select an inbox item or press</p>
            <kbd style={styles.kbd}>Cmd+K</kbd>
            <p style={styles.placeholderText}>to capture something new</p>
          </div>
        )}
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
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
  kbd: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.accent,
  },
};
