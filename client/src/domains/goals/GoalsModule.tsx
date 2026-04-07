/**
 * Goals module: combines ListPane + DetailPane for the goals domain.
 * Section 9.1: List Pane (240px, resizable) + Detail Pane.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { GoalList } from './GoalList';
import { GoalDetail } from './GoalDetail';
import { GoalCreate } from './GoalCreate';
import { tokens } from '../../styles/tokens';
import type { GoalResponse } from '../../types';

export function GoalsModule() {
  const [selectedGoal, setSelectedGoal] = useState<GoalResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedGoal(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Goals">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedGoal(null); }} style={styles.addButton}>
            + New Goal
          </button>
        </div>
        <GoalList
          selectedId={selectedGoal?.node_id ?? null}
          onSelect={(g) => { setSelectedGoal(g); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane nodeId={selectedGoal?.node_id}>
        {creating ? (
          <GoalCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedGoal ? (
          <GoalDetail goal={selectedGoal} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a goal or create a new one</p>
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
