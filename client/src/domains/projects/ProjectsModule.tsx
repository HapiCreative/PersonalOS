/**
 * Projects module: combines ListPane + DetailPane for the projects domain.
 * Section 9.1: List Pane (240px, resizable) + Detail Pane.
 * Phase 8: Lightweight project containers.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { ProjectList } from './ProjectList';
import { ProjectDetail } from './ProjectDetail';
import { ProjectCreate } from './ProjectCreate';
import { tokens } from '../../styles/tokens';
import type { ProjectResponse } from '../../types';

export function ProjectsModule() {
  const [selectedProject, setSelectedProject] = useState<ProjectResponse | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [creating, setCreating] = useState(false);

  const handleUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setSelectedProject(null);
    setCreating(false);
  }, []);

  return (
    <>
      <ListPane title="Projects">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelectedProject(null); }} style={styles.addButton}>
            + New Project
          </button>
        </div>
        <ProjectList
          selectedId={selectedProject?.node_id ?? null}
          onSelect={(p) => { setSelectedProject(p); setCreating(false); }}
          refreshKey={refreshKey}
        />
      </ListPane>
      <DetailPane nodeId={selectedProject?.node_id}>
        {creating ? (
          <ProjectCreate
            onCreated={handleUpdated}
            onCancel={() => setCreating(false)}
          />
        ) : selectedProject ? (
          <ProjectDetail project={selectedProject} onUpdated={handleUpdated} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a project or create a new one</p>
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
