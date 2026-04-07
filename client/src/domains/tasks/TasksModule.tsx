/**
 * Tasks module: combines ListPane + DetailPane for the tasks domain.
 * Section 9.1: List Pane (240px, resizable) + Detail Pane.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { TaskList } from './TaskList';
import { TaskDetail } from './TaskDetail';
import { TaskCreate } from './TaskCreate';
import { tokens } from '../../styles/tokens';
import type { TaskResponse } from '../../types';

export function TasksModule() {
  const [selectedTask, setSelectedTask] = useState<TaskResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedTask(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Tasks">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedTask(null); }} style={styles.addButton}>
            + New Task
          </button>
        </div>
        <TaskList
          selectedId={selectedTask?.node_id ?? null}
          onSelect={(t) => { setSelectedTask(t); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane>
        {creating ? (
          <TaskCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedTask ? (
          <TaskDetail task={selectedTask} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a task or create a new one</p>
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
