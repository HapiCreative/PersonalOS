/**
 * Project detail view with linked goals/tasks.
 * Invariant G-05: belongs_to edges restricted to goal→project, task→project.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { projectsApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { ProjectResponse, ProjectWithLinksResponse, ProjectLinkedItemResponse, ProjectStatus } from '../../types';

const STATUS_COLORS: Record<ProjectStatus, string> = {
  active: tokens.colors.accent,
  completed: tokens.colors.success,
  archived: tokens.colors.textMuted,
};

interface ProjectDetailProps {
  project: ProjectResponse;
  onUpdated: () => void;
}

export function ProjectDetail({ project, onUpdated }: ProjectDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(project.title);
  const [description, setDescription] = useState(project.description || '');
  const [tags, setTags] = useState(project.tags.join(', '));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailedProject, setDetailedProject] = useState<ProjectWithLinksResponse | null>(null);

  useEffect(() => {
    setTitle(project.title);
    setDescription(project.description || '');
    setTags(project.tags.join(', '));
    setError(null);
    setEditing(false);
    projectsApi.get(project.node_id).then(setDetailedProject).catch(() => setDetailedProject(null));
  }, [project]);

  const currentProject = detailedProject || project;
  const linkedItems: ProjectLinkedItemResponse[] = detailedProject?.linked_items || [];
  const linkedGoals = linkedItems.filter((i) => i.node_type === 'goal');
  const linkedTasks = linkedItems.filter((i) => i.node_type === 'task');

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await projectsApi.update(project.node_id, {
        title,
        description: description || null,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: ProjectStatus) => {
    setError(null);
    try {
      await projectsApi.update(project.node_id, { status: newStatus });
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Status change failed');
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        {editing ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={styles.titleInput}
            autoFocus
          />
        ) : (
          <h2 style={styles.title}>{currentProject.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{project.node_id.slice(0, 8)}</span>
          <span style={styles.date}>Created {new Date(project.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Status row */}
      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Status:</span>
        <span style={{
          ...styles.currentStatus,
          color: STATUS_COLORS[currentProject.status],
          borderColor: STATUS_COLORS[currentProject.status],
        }}>
          {currentProject.status}
        </span>
        {currentProject.status === 'active' && (
          <button onClick={() => handleStatusChange('completed')} style={styles.transitionButton}>
            Mark Completed
          </button>
        )}
        {currentProject.status === 'active' && (
          <button onClick={() => handleStatusChange('archived')} style={styles.transitionButton}>
            Archive
          </button>
        )}
        {currentProject.status === 'archived' && (
          <button onClick={() => handleStatusChange('active')} style={styles.transitionButton}>
            Reactivate
          </button>
        )}
      </div>

      {/* Tags */}
      {(currentProject.tags.length > 0 || editing) && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Tags</h3>
          {editing ? (
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              style={styles.textInput}
              placeholder="Comma-separated tags"
            />
          ) : (
            <div style={styles.tagRow}>
              {currentProject.tags.map((tag, i) => (
                <span key={i} style={styles.tag}>{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Description */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Description</h3>
          {!editing ? (
            <button onClick={() => setEditing(true)} style={styles.editButton}>Edit</button>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleSave} disabled={saving} style={styles.saveButton}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => { setEditing(false); setTitle(project.title); setDescription(project.description || ''); setTags(project.tags.join(', ')); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={styles.textArea}
            rows={6}
          />
        ) : (
          <p style={styles.content}>{currentProject.description || 'No description'}</p>
        )}
      </div>

      {/* Linked Goals (via belongs_to edges) - Invariant G-05 */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Linked Goals ({linkedGoals.length})</h3>
        {linkedGoals.length === 0 ? (
          <p style={styles.content}>No goals linked. Create a belongs_to edge from a goal to this project.</p>
        ) : (
          <div style={styles.itemList}>
            {linkedGoals.map((item) => (
              <div key={item.node_id} style={styles.linkedItem}>
                <span style={styles.itemIcon}>◎</span>
                <span style={styles.itemTitle}>{item.title}</span>
                <span style={{
                  ...styles.itemStatus,
                  color: item.status === 'active' ? tokens.colors.accent
                    : item.status === 'completed' ? tokens.colors.success
                    : tokens.colors.textMuted,
                }}>{item.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Linked Tasks (via belongs_to edges) - Invariant G-05 */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Linked Tasks ({linkedTasks.length})</h3>
        {linkedTasks.length === 0 ? (
          <p style={styles.content}>No tasks linked. Create a belongs_to edge from a task to this project.</p>
        ) : (
          <div style={styles.itemList}>
            {linkedTasks.map((item) => (
              <div key={item.node_id} style={styles.linkedItem}>
                <span style={{
                  ...styles.itemIcon,
                  color: item.status === 'done' ? tokens.colors.success
                    : item.status === 'in_progress' ? tokens.colors.accent
                    : tokens.colors.textMuted,
                }}>
                  {item.status === 'done' ? '✓' : item.status === 'in_progress' ? '▸' : '○'}
                </span>
                <span style={styles.itemTitle}>{item.title}</span>
                <span style={styles.itemStatus}>{item.status}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={project.node_id} />
      <BacklinksDisplay nodeId={project.node_id} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 640 },
  header: { marginBottom: 16 },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  titleInput: {
    width: '100%',
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '4px 8px',
    marginBottom: 8,
  },
  meta: { display: 'flex', gap: 12, alignItems: 'center' },
  nodeId: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  date: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  error: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.error}15`,
    border: `1px solid ${tokens.colors.error}30`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    padding: '12px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
    borderBottom: `1px solid ${tokens.colors.border}`,
    flexWrap: 'wrap' as const,
  },
  statusLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
  },
  currentStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '3px 8px',
    borderRadius: tokens.radius,
    border: '1px solid',
    textTransform: 'capitalize' as const,
  },
  transitionButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    cursor: 'pointer',
    background: 'none',
    color: tokens.colors.text,
  },
  section: { marginBottom: 20 },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.text,
  },
  editButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  saveButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
  },
  textInput: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '8px 10px',
  },
  textArea: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '10px 12px',
    resize: 'vertical' as const,
    lineHeight: 1.5,
  },
  content: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap' as const,
  },
  tagRow: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    padding: '2px 8px',
    borderRadius: tokens.radius,
  },
  itemList: { display: 'flex', flexDirection: 'column', gap: 2 },
  linkedItem: {
    display: 'flex',
    gap: 10,
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
    alignItems: 'center',
  },
  itemIcon: {
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    minWidth: 16,
    textAlign: 'center' as const,
    color: tokens.colors.accent,
  },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    flex: 1,
  },
  itemStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
    color: tokens.colors.textMuted,
  },
};
