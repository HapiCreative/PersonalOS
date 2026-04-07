/**
 * Task detail view with status transitions, editing, and execution events.
 * Invariant B-03: State machine transitions with validation feedback.
 * Invariant S-02: Recurring + done = rejected.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { tasksApi, executionEventsApi, projectsApi, edgesApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { TaskResponse, TaskStatus, TaskPriority, TaskExecutionEventResponse, ProjectResponse } from '../../types';

const PRIORITY_OPTIONS: TaskPriority[] = ['low', 'medium', 'high', 'urgent'];

// Invariant B-03: Valid state transitions
const VALID_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  todo: ['in_progress', 'cancelled'],
  in_progress: ['done', 'cancelled'],
  done: [],
  cancelled: [],
};

const STATUS_COLORS: Record<TaskStatus, string> = {
  todo: tokens.colors.textMuted,
  in_progress: tokens.colors.accent,
  done: tokens.colors.success,
  cancelled: tokens.colors.textMuted,
};

interface TaskDetailProps {
  task: TaskResponse;
  onUpdated: () => void;
}

export function TaskDetail({ task, onUpdated }: TaskDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [notes, setNotes] = useState(task.notes || '');
  const [priority, setPriority] = useState<TaskPriority>(task.priority);
  const [dueDate, setDueDate] = useState(task.due_date || '');
  const [recurrence, setRecurrence] = useState(task.recurrence || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [events, setEvents] = useState<TaskExecutionEventResponse[]>([]);
  const [showLogEvent, setShowLogEvent] = useState(false);
  // Phase 8: Project selector
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null);
  const [assigningProject, setAssigningProject] = useState(false);

  useEffect(() => {
    setTitle(task.title);
    setNotes(task.notes || '');
    setPriority(task.priority);
    setDueDate(task.due_date || '');
    setRecurrence(task.recurrence || '');
    setError(null);
    setEditing(false);
    // Load execution events
    executionEventsApi.list({ task_id: task.node_id }).then((res) => {
      setEvents(res.items);
    }).catch(() => setEvents([]));
    // Phase 8: Load projects and current assignment
    projectsApi.list({ status: 'active' }).then((res) => setProjects(res.items)).catch(() => setProjects([]));
    edgesApi.getForNode(task.node_id, { direction: 'outgoing', relation_type: 'belongs_to' })
      .then((res) => {
        const belongsTo = res.items.find((e) => e.relation_type === 'belongs_to');
        setCurrentProjectId(belongsTo?.target_id ?? null);
      })
      .catch(() => setCurrentProjectId(null));
  }, [task]);

  const handleTransition = async (newStatus: TaskStatus) => {
    setError(null);
    try {
      await tasksApi.transition(task.node_id, newStatus);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Transition failed');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await tasksApi.update(task.node_id, {
        title,
        priority,
        due_date: dueDate || null,
        recurrence: recurrence || null,
        notes: notes || null,
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleLogEvent = async (eventType: 'completed' | 'skipped' | 'deferred') => {
    setError(null);
    try {
      await executionEventsApi.create({
        task_id: task.node_id,
        event_type: eventType,
        expected_for_date: new Date().toISOString().split('T')[0],
      });
      setShowLogEvent(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Failed to log event');
    }
  };

  // Phase 8: Assign task to project via belongs_to edge (Invariant G-05)
  const handleAssignProject = async (projectNodeId: string) => {
    setAssigningProject(true);
    setError(null);
    try {
      // Remove existing belongs_to edge if any
      if (currentProjectId) {
        const existing = await edgesApi.getForNode(task.node_id, { direction: 'outgoing', relation_type: 'belongs_to' });
        for (const edge of existing.items) {
          if (edge.relation_type === 'belongs_to') {
            await edgesApi.delete(edge.id);
          }
        }
      }
      // Create new belongs_to edge if not "none"
      if (projectNodeId !== '') {
        await edgesApi.create({
          source_id: task.node_id,
          target_id: projectNodeId,
          relation_type: 'belongs_to',
        });
        setCurrentProjectId(projectNodeId);
      } else {
        setCurrentProjectId(null);
      }
    } catch (e: any) {
      setError(e.message || 'Failed to assign project');
    } finally {
      setAssigningProject(false);
    }
  };

  const allowedTransitions = VALID_TRANSITIONS[task.status] || [];
  // Invariant S-02: Filter out 'done' for recurring tasks
  const filteredTransitions = task.is_recurring
    ? allowedTransitions.filter((s) => s !== 'done')
    : allowedTransitions;

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
          <h2 style={styles.title}>{task.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{task.node_id.slice(0, 8)}</span>
          {task.is_recurring && <span style={styles.recurringTag}>Recurring</span>}
          <span style={styles.date}>Created {new Date(task.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Status & transitions */}
      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Status:</span>
        <span style={{
          ...styles.currentStatus,
          color: STATUS_COLORS[task.status],
          borderColor: STATUS_COLORS[task.status],
        }}>
          {task.status.replace('_', ' ')}
        </span>
        {filteredTransitions.map((s) => (
          <button
            key={s}
            onClick={() => handleTransition(s)}
            style={styles.transitionButton}
          >
            → {s.replace('_', ' ')}
          </button>
        ))}
      </div>

      {/* Priority / Due / Recurrence row */}
      <div style={styles.fieldRow}>
        {editing ? (
          <>
            <label style={styles.fieldLabel}>Priority:</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
              style={styles.select}
            >
              {PRIORITY_OPTIONS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <label style={styles.fieldLabel}>Due:</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              style={styles.dateInput}
            />
            <label style={styles.fieldLabel}>Recurrence:</label>
            <input
              type="text"
              value={recurrence}
              onChange={(e) => setRecurrence(e.target.value)}
              placeholder="cron expression"
              style={styles.textInput}
            />
          </>
        ) : (
          <>
            <span style={styles.fieldLabel}>Priority:</span>
            <span style={styles.fieldValue}>{task.priority}</span>
            {task.due_date && (
              <>
                <span style={styles.fieldLabel}>Due:</span>
                <span style={styles.fieldValue}>{task.due_date}</span>
              </>
            )}
            {task.recurrence && (
              <>
                <span style={styles.fieldLabel}>Recurrence:</span>
                <span style={styles.fieldValue}>{task.recurrence}</span>
              </>
            )}
          </>
        )}
      </div>

      {/* Phase 8: Project selector - Invariant G-05 */}
      {projects.length > 0 && (
        <div style={styles.fieldRow}>
          <span style={styles.fieldLabel}>Project:</span>
          <select
            value={currentProjectId || ''}
            onChange={(e) => handleAssignProject(e.target.value)}
            disabled={assigningProject}
            style={styles.select}
          >
            <option value="">None</option>
            {projects.map((p) => (
              <option key={p.node_id} value={p.node_id}>{p.title}</option>
            ))}
          </select>
          {assigningProject && <span style={styles.fieldLabel}>Saving...</span>}
        </div>
      )}

      {/* Notes */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Notes</h3>
          {!editing ? (
            <button onClick={() => setEditing(true)} style={styles.editButton}>Edit</button>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleSave} disabled={saving} style={styles.saveButton}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => { setEditing(false); setTitle(task.title); setNotes(task.notes || ''); setPriority(task.priority); setDueDate(task.due_date || ''); setRecurrence(task.recurrence || ''); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={styles.textArea}
            rows={6}
          />
        ) : (
          <p style={styles.content}>{task.notes || 'No notes'}</p>
        )}
      </div>

      {/* Execution Events (Temporal) */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Execution History</h3>
          <button
            onClick={() => setShowLogEvent(!showLogEvent)}
            style={styles.editButton}
          >
            {showLogEvent ? 'Cancel' : 'Log Event'}
          </button>
        </div>
        {showLogEvent && (
          <div style={styles.logEventRow}>
            <button onClick={() => handleLogEvent('completed')} style={{ ...styles.eventButton, color: tokens.colors.success }}>Completed</button>
            <button onClick={() => handleLogEvent('skipped')} style={{ ...styles.eventButton, color: tokens.colors.warning }}>Skipped</button>
            <button onClick={() => handleLogEvent('deferred')} style={{ ...styles.eventButton, color: tokens.colors.textMuted }}>Deferred</button>
          </div>
        )}
        {events.length === 0 ? (
          <p style={styles.content}>No execution events</p>
        ) : (
          <div style={styles.eventList}>
            {events.map((ev) => (
              <div key={ev.id} style={styles.eventItem}>
                <span style={{
                  ...styles.eventType,
                  color: ev.event_type === 'completed' ? tokens.colors.success
                    : ev.event_type === 'skipped' ? tokens.colors.warning
                    : tokens.colors.textMuted,
                }}>
                  {ev.event_type}
                </span>
                <span style={styles.eventDate}>{ev.expected_for_date}</span>
                <span style={styles.eventTimestamp}>
                  {new Date(ev.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edges / Backlinks (Phase 2) */}
      <EdgeChips nodeId={task.node_id} />
      <BacklinksDisplay nodeId={task.node_id} />
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
  recurringTag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    padding: '2px 6px',
    border: `1px solid ${tokens.colors.accent}`,
    borderRadius: tokens.radius,
  },
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
    textTransform: 'capitalize' as const,
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    flexWrap: 'wrap' as const,
  },
  fieldLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
  },
  fieldValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.text,
  },
  select: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
  },
  dateInput: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
  },
  textInput: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
    width: 120,
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
  logEventRow: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  },
  eventButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    cursor: 'pointer',
    background: 'none',
  },
  eventList: { display: 'flex', flexDirection: 'column', gap: 4 },
  eventItem: {
    display: 'flex',
    gap: 12,
    padding: '6px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
    alignItems: 'center',
  },
  eventType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    minWidth: 70,
    textTransform: 'capitalize' as const,
  },
  eventDate: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.text,
  },
  eventTimestamp: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
};
