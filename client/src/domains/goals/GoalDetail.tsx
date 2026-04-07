/**
 * Goal detail view with milestones, progress bar, and linked tasks.
 * Invariant D-03: progress is CACHED DERIVED, non-canonical.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { goalsApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { GoalResponse, GoalWithTasksResponse, GoalLinkedTaskResponse, GoalStatus } from '../../types';

const STATUS_COLORS: Record<GoalStatus, string> = {
  active: tokens.colors.accent,
  completed: tokens.colors.success,
  archived: tokens.colors.textMuted,
};

const TASK_STATUS_COLORS: Record<string, string> = {
  todo: tokens.colors.textMuted,
  in_progress: tokens.colors.accent,
  done: tokens.colors.success,
  cancelled: tokens.colors.textMuted,
};

interface GoalDetailProps {
  goal: GoalResponse;
  onUpdated: () => void;
}

export function GoalDetail({ goal, onUpdated }: GoalDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(goal.title);
  const [notes, setNotes] = useState(goal.notes || '');
  const [startDate, setStartDate] = useState(goal.start_date || '');
  const [endDate, setEndDate] = useState(goal.end_date || '');
  const [timeframeLabel, setTimeframeLabel] = useState(goal.timeframe_label || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailedGoal, setDetailedGoal] = useState<GoalWithTasksResponse | null>(null);

  useEffect(() => {
    setTitle(goal.title);
    setNotes(goal.notes || '');
    setStartDate(goal.start_date || '');
    setEndDate(goal.end_date || '');
    setTimeframeLabel(goal.timeframe_label || '');
    setError(null);
    setEditing(false);
    // Fetch detailed view with linked tasks
    goalsApi.get(goal.node_id).then(setDetailedGoal).catch(() => setDetailedGoal(null));
  }, [goal]);

  const currentGoal = detailedGoal || goal;
  const linkedTasks: GoalLinkedTaskResponse[] = detailedGoal?.linked_tasks || [];

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await goalsApi.update(goal.node_id, {
        title,
        start_date: startDate || null,
        end_date: endDate || null,
        timeframe_label: timeframeLabel || null,
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

  const handleStatusChange = async (newStatus: GoalStatus) => {
    setError(null);
    try {
      await goalsApi.update(goal.node_id, { status: newStatus });
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Status change failed');
    }
  };

  const handleRefreshProgress = async () => {
    try {
      await goalsApi.refreshProgress(goal.node_id);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Refresh failed');
    }
  };

  const progressPct = Math.round(currentGoal.progress * 100);

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
          <h2 style={styles.title}>{currentGoal.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{goal.node_id.slice(0, 8)}</span>
          <span style={styles.date}>Created {new Date(goal.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Status row */}
      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Status:</span>
        <span style={{
          ...styles.currentStatus,
          color: STATUS_COLORS[currentGoal.status],
          borderColor: STATUS_COLORS[currentGoal.status],
        }}>
          {currentGoal.status}
        </span>
        {currentGoal.status === 'active' && (
          <button onClick={() => handleStatusChange('completed')} style={styles.transitionButton}>
            Mark Completed
          </button>
        )}
        {currentGoal.status === 'active' && (
          <button onClick={() => handleStatusChange('archived')} style={styles.transitionButton}>
            Archive
          </button>
        )}
        {currentGoal.status === 'archived' && (
          <button onClick={() => handleStatusChange('active')} style={styles.transitionButton}>
            Reactivate
          </button>
        )}
      </div>

      {/* Progress bar - Invariant D-03: Non-canonical CACHED DERIVED */}
      <div style={styles.progressSection}>
        <div style={styles.progressHeader}>
          <span style={styles.sectionTitle}>Progress</span>
          <span style={styles.progressValue}>{progressPct}%</span>
          <button onClick={handleRefreshProgress} style={styles.refreshButton} title="Refresh progress">
            ↻
          </button>
        </div>
        <div style={styles.progressBarContainer}>
          <div style={{
            ...styles.progressBarFill,
            width: `${progressPct}%`,
            background: currentGoal.status === 'completed' ? tokens.colors.success : tokens.colors.accent,
          }} />
        </div>
      </div>

      {/* Timeframe fields */}
      <div style={styles.fieldRow}>
        {editing ? (
          <>
            <div style={styles.fieldGroup}>
              <label style={styles.fieldLabel}>Start:</label>
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={styles.dateInput} />
            </div>
            <div style={styles.fieldGroup}>
              <label style={styles.fieldLabel}>End:</label>
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={styles.dateInput} />
            </div>
            <div style={styles.fieldGroup}>
              <label style={styles.fieldLabel}>Timeframe:</label>
              <input value={timeframeLabel} onChange={(e) => setTimeframeLabel(e.target.value)} style={styles.textInput} placeholder="e.g. Q1 2026" />
            </div>
          </>
        ) : (
          <>
            {currentGoal.start_date && (
              <>
                <span style={styles.fieldLabel}>Start:</span>
                <span style={styles.fieldValue}>{currentGoal.start_date}</span>
              </>
            )}
            {currentGoal.end_date && (
              <>
                <span style={styles.fieldLabel}>End:</span>
                <span style={styles.fieldValue}>{currentGoal.end_date}</span>
              </>
            )}
            {currentGoal.timeframe_label && (
              <>
                <span style={styles.fieldLabel}>Timeframe:</span>
                <span style={styles.fieldValue}>{currentGoal.timeframe_label}</span>
              </>
            )}
          </>
        )}
      </div>

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
              <button onClick={() => { setEditing(false); setTitle(goal.title); setNotes(goal.notes || ''); setStartDate(goal.start_date || ''); setEndDate(goal.end_date || ''); setTimeframeLabel(goal.timeframe_label || ''); }} style={styles.cancelButton}>Cancel</button>
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
          <p style={styles.content}>{currentGoal.notes || 'No notes'}</p>
        )}
      </div>

      {/* Milestones */}
      {currentGoal.milestones && currentGoal.milestones.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Milestones</h3>
          <div style={styles.milestoneList}>
            {currentGoal.milestones.map((m, i) => (
              <div key={i} style={styles.milestoneItem}>
                <span style={styles.milestoneDot}>
                  {(m as any).completed ? '●' : '○'}
                </span>
                <span style={styles.milestoneText}>
                  {(m as any).title || (m as any).name || JSON.stringify(m)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Linked Tasks */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Linked Tasks ({linkedTasks.length})</h3>
        {linkedTasks.length === 0 ? (
          <p style={styles.content}>No tasks linked to this goal. Use edges to link tasks via goal_tracks_task.</p>
        ) : (
          <div style={styles.taskList}>
            {linkedTasks.map((task) => (
              <div key={task.node_id} style={styles.taskItem}>
                <span style={{
                  ...styles.taskStatus,
                  color: TASK_STATUS_COLORS[task.status] || tokens.colors.textMuted,
                }}>
                  {task.status === 'done' ? '✓' : task.status === 'in_progress' ? '▸' : '○'}
                </span>
                <span style={styles.taskTitle}>{task.title}</span>
                <span style={{
                  ...styles.taskPriority,
                  color: task.priority === 'urgent' ? tokens.colors.error
                    : task.priority === 'high' ? tokens.colors.warning
                    : tokens.colors.textMuted,
                }}>
                  {task.priority}
                </span>
                {task.due_date && (
                  <span style={styles.taskDue}>{task.due_date}</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={goal.node_id} />
      <BacklinksDisplay nodeId={goal.node_id} />
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
  progressSection: { marginBottom: 16 },
  progressHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  progressValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.accent,
    fontWeight: 600,
  },
  refreshButton: {
    padding: '2px 6px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    cursor: 'pointer',
    background: 'none',
    color: tokens.colors.textMuted,
  },
  progressBarContainer: {
    width: '100%',
    height: 6,
    background: tokens.colors.border,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 0.3s ease',
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    flexWrap: 'wrap' as const,
  },
  fieldGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
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
  milestoneList: { display: 'flex', flexDirection: 'column', gap: 6 },
  milestoneItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 0',
  },
  milestoneDot: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.accent,
  },
  milestoneText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  taskList: { display: 'flex', flexDirection: 'column', gap: 2 },
  taskItem: {
    display: 'flex',
    gap: 10,
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
    alignItems: 'center',
  },
  taskStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    minWidth: 16,
    textAlign: 'center' as const,
  },
  taskTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    flex: 1,
  },
  taskPriority: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
  },
  taskDue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
};
