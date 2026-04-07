/**
 * Task creation form with template support.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { tasksApi, templatesApi, projectsApi, edgesApi } from '../../api/endpoints';
import type { TaskPriority, TemplateResponse, ProjectResponse } from '../../types';

const PRIORITY_OPTIONS: TaskPriority[] = ['low', 'medium', 'high', 'urgent'];

interface TaskCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function TaskCreate({ onCreated, onCancel }: TaskCreateProps) {
  const [title, setTitle] = useState('');
  const [notes, setNotes] = useState('');
  const [priority, setPriority] = useState<TaskPriority>('medium');
  const [dueDate, setDueDate] = useState('');
  const [recurrence, setRecurrence] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateResponse[]>([]);
  // Phase 8: Project selector
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');

  useEffect(() => {
    templatesApi.list({ target_type: 'task' }).then((res) => {
      setTemplates(res.items);
    }).catch(() => {});
    projectsApi.list({ status: 'active' }).then((res) => setProjects(res.items)).catch(() => setProjects([]));
  }, []);

  const applyTemplate = (template: TemplateResponse) => {
    const s = template.structure as Record<string, any>;
    if (s.title) setTitle(s.title);
    if (s.notes) setNotes(s.notes);
    if (s.priority) setPriority(s.priority);
    if (s.recurrence) setRecurrence(s.recurrence);
  };

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const newTask = await tasksApi.create({
        title: title.trim(),
        priority,
        due_date: dueDate || undefined,
        recurrence: recurrence || undefined,
        notes: notes || undefined,
      });
      // Phase 8: Assign to project via belongs_to edge (Invariant G-05)
      if (selectedProjectId) {
        await edgesApi.create({
          source_id: newTask.node_id,
          target_id: selectedProjectId,
          relation_type: 'belongs_to',
        });
      }
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create task');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Task</h2>

      {error && <div style={styles.error}>{error}</div>}

      {templates.length > 0 && (
        <div style={styles.templateRow}>
          <span style={styles.label}>Template:</span>
          {templates.map((t) => (
            <button key={t.id} onClick={() => applyTemplate(t)} style={styles.templateButton}>
              {t.name}
            </button>
          ))}
        </div>
      )}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={styles.input}
          placeholder="Task title"
          autoFocus
        />
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Priority</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)} style={styles.select}>
            {PRIORITY_OPTIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Due Date</label>
          <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} style={styles.input} />
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Recurrence</label>
          <input
            value={recurrence}
            onChange={(e) => setRecurrence(e.target.value)}
            style={styles.input}
            placeholder="cron expression"
          />
        </div>
      </div>

      {/* Phase 8: Project selector */}
      {projects.length > 0 && (
        <div style={styles.field}>
          <label style={styles.label}>Project</label>
          <select
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            style={styles.select}
          >
            <option value="">None</option>
            {projects.map((p) => (
              <option key={p.node_id} value={p.node_id}>{p.title}</option>
            ))}
          </select>
        </div>
      )}

      <div style={styles.field}>
        <label style={styles.label}>Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          style={styles.textArea}
          rows={4}
          placeholder="Optional notes..."
        />
      </div>

      <div style={styles.actions}>
        <button onClick={handleSubmit} disabled={saving || !title.trim()} style={styles.saveButton}>
          {saving ? 'Creating...' : 'Create Task'}
        </button>
        <button onClick={onCancel} style={styles.cancelButton}>Cancel</button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 560, padding: '0' },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    marginBottom: 16,
  },
  error: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.error}15`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  templateRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
    flexWrap: 'wrap' as const,
  },
  templateButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.violet}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.violet,
    cursor: 'pointer',
    background: 'none',
  },
  field: { marginBottom: 12 },
  label: {
    display: 'block',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
    color: tokens.colors.textMuted,
    marginBottom: 4,
  },
  input: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '8px 10px',
  },
  select: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
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
    padding: '8px 10px',
    resize: 'vertical' as const,
    lineHeight: 1.5,
  },
  row: { display: 'flex', gap: 12 },
  actions: { display: 'flex', gap: 8, marginTop: 16 },
  saveButton: {
    padding: '8px 16px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '8px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
  },
};
