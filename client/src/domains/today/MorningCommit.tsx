/**
 * Morning Commit UI (Section 5.1 — Phase 7).
 * Commit stage of the 4-stage daily cycle.
 *
 * Workflow:
 * 1. System suggests tasks (signal score, due dates, goal drift)
 * 2. User selects 1-3 priorities + optional secondary tasks
 * 3. Sets intention (optional)
 * 4. Produces daily_plans record
 *
 * Invariant U-04: Focus section cap 1-3 tasks.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { morningCommitApi } from '../../api/endpoints';
import type {
  MorningCommitSuggestionsResponse,
  SuggestedTaskResponse,
} from '../../types';

const REASON_LABELS: Record<string, string> = {
  overdue: 'Overdue',
  due_today: 'Due Today',
  high_signal: 'High Priority',
  goal_drift: 'Goal Needs Progress',
};

const REASON_COLORS: Record<string, string> = {
  overdue: tokens.colors.error,
  due_today: tokens.colors.warning,
  high_signal: tokens.colors.accent,
  goal_drift: tokens.colors.violet,
};

interface MorningCommitProps {
  onCommitted: () => void;
  onSkip: () => void;
}

export function MorningCommit({ onCommitted, onSkip }: MorningCommitProps) {
  const [data, setData] = useState<MorningCommitSuggestionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [intention, setIntention] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchSuggestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await morningCommitApi.getSuggestions();
      setData(result);
      // If there's an existing plan, pre-select its tasks
      if (result.existing_plan?.selected_task_ids) {
        setSelectedIds(new Set(result.existing_plan.selected_task_ids as string[]));
        if (result.existing_plan.intention_text) {
          setIntention(result.existing_plan.intention_text as string);
        }
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load suggestions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSuggestions();
  }, [fetchSuggestions]);

  const toggleTask = (nodeId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const handleCommit = async () => {
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    try {
      await morningCommitApi.commit(
        Array.from(selectedIds),
        intention || undefined,
      );
      onCommitted();
    } catch (e: any) {
      setError(e.message || 'Failed to commit plan');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingState}>Loading morning suggestions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.errorState}>
          <p>{error}</p>
          <button onClick={fetchSuggestions} style={styles.secondaryButton}>Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.heading}>Morning Commit</h2>
          <p style={styles.subtitle}>
            {new Date(data.date).toLocaleDateString('en-US', {
              weekday: 'long', month: 'long', day: 'numeric',
            })}
          </p>
        </div>

        {/* AI Briefing */}
        <div style={styles.briefingCard}>
          <div style={styles.briefingHeader}>Daily Briefing</div>
          <ul style={styles.briefingList}>
            {data.ai_briefing.map((bullet, i) => (
              <li key={i} style={styles.briefingItem}>{bullet}</li>
            ))}
          </ul>
        </div>

        {/* Task Selection */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <span style={styles.sectionTitle}>Select Your Priorities</span>
            <span style={styles.selectionCount}>
              {selectedIds.size} selected
              {selectedIds.size > 0 && selectedIds.size <= 3 && ' (good)'}
              {selectedIds.size > 3 && ' (consider focusing)'}
            </span>
          </div>

          {data.suggested_tasks.length === 0 ? (
            <div style={styles.emptyTasks}>
              <p style={styles.emptyText}>No tasks to suggest. Create some tasks first!</p>
            </div>
          ) : (
            <div style={styles.taskList}>
              {data.suggested_tasks.map((task) => (
                <TaskSuggestionCard
                  key={task.node_id}
                  task={task}
                  selected={selectedIds.has(task.node_id)}
                  onToggle={() => toggleTask(task.node_id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Intention */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <span style={styles.sectionTitle}>Set Your Intention</span>
            <span style={styles.optionalLabel}>optional</span>
          </div>
          <textarea
            value={intention}
            onChange={(e) => setIntention(e.target.value)}
            placeholder="What do you want to accomplish today? What mindset will help you succeed?"
            style={styles.intentionInput}
            rows={3}
          />
        </div>

        {/* Actions */}
        <div style={styles.actions}>
          <button
            onClick={onSkip}
            style={styles.secondaryButton}
          >
            Skip for now
          </button>
          <button
            onClick={handleCommit}
            disabled={selectedIds.size === 0 || submitting}
            style={{
              ...styles.commitButton,
              opacity: selectedIds.size === 0 || submitting ? 0.5 : 1,
            }}
          >
            {submitting ? 'Committing...' : data.existing_plan ? 'Update Plan' : 'Commit to Plan'}
          </button>
        </div>
      </div>
    </div>
  );
}

function TaskSuggestionCard({
  task,
  selected,
  onToggle,
}: {
  task: SuggestedTaskResponse;
  selected: boolean;
  onToggle: () => void;
}) {
  const reasonColor = REASON_COLORS[task.reason] || tokens.colors.textMuted;
  const reasonLabel = REASON_LABELS[task.reason] || task.reason;

  return (
    <button
      onClick={onToggle}
      style={{
        ...styles.taskCard,
        borderLeftColor: selected ? tokens.colors.accent : tokens.colors.border,
        background: selected ? `${tokens.colors.accent}08` : 'transparent',
      }}
    >
      <div style={styles.taskCardTop}>
        <div style={{
          ...styles.checkbox,
          background: selected ? tokens.colors.accent : 'transparent',
          borderColor: selected ? tokens.colors.accent : tokens.colors.border,
        }}>
          {selected && <span style={styles.checkmark}>&#10003;</span>}
        </div>
        <div style={styles.taskInfo}>
          <span style={styles.taskTitle}>{task.title}</span>
          <div style={styles.taskMeta}>
            <span style={{
              ...styles.reasonBadge,
              color: reasonColor,
              borderColor: reasonColor,
            }}>
              {reasonLabel}
            </span>
            <span style={styles.priorityBadge}>{task.priority}</span>
            {task.due_date && (
              <span style={styles.dueDateLabel}>
                Due {task.due_date}
              </span>
            )}
            {task.goal_title && (
              <span style={styles.goalLabel}>
                Goal: {task.goal_title}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    height: '100%',
    overflowY: 'auto',
    background: tokens.colors.background,
  },
  inner: {
    maxWidth: 640,
    margin: '0 auto',
    padding: '24px 20px',
  },
  loadingState: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
  },
  errorState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    gap: 12,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.error,
  },
  header: {
    marginBottom: 24,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
    margin: 0,
    marginBottom: 4,
  },
  subtitle: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.textMuted,
    margin: 0,
  },
  briefingCard: {
    background: `${tokens.colors.violet}08`,
    border: `1px solid ${tokens.colors.violet}30`,
    borderRadius: tokens.radius,
    padding: '14px 16px',
    marginBottom: 20,
  },
  briefingHeader: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.violet,
    marginBottom: 10,
  },
  briefingList: {
    margin: 0,
    paddingLeft: 18,
    listStyle: 'disc',
  },
  briefingItem: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    lineHeight: 1.6,
  },
  sectionCard: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    overflow: 'hidden',
    marginBottom: 16,
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 14px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.text,
  },
  selectionCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  optionalLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    fontStyle: 'italic',
  },
  emptyTasks: {
    padding: '24px 14px',
    textAlign: 'center' as const,
  },
  emptyText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
  },
  taskCard: {
    display: 'flex',
    alignItems: 'flex-start',
    width: '100%',
    padding: '10px 14px',
    borderLeft: '3px solid',
    borderBottom: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
    textAlign: 'left' as const,
    transition: 'background 0.1s',
    background: 'none',
    border: 'none',
    borderLeftStyle: 'solid',
    borderLeftWidth: 3,
    borderBottomStyle: 'solid',
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
  },
  taskCardTop: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    width: '100%',
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: tokens.radius,
    border: '2px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 1,
  },
  checkmark: {
    fontSize: 11,
    color: tokens.colors.background,
    fontWeight: 700,
  },
  taskInfo: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  taskTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  taskMeta: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    alignItems: 'center',
  },
  reasonBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    padding: '1px 5px',
    border: '1px solid',
    borderRadius: tokens.radius,
  },
  priorityBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    padding: '1px 5px',
    background: `${tokens.colors.textMuted}15`,
    borderRadius: tokens.radius,
  },
  dueDateLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  goalLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
  },
  intentionInput: {
    width: '100%',
    padding: '10px 14px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    background: tokens.colors.background,
    border: 'none',
    outline: 'none',
    resize: 'vertical' as const,
    lineHeight: 1.5,
    boxSizing: 'border-box' as const,
  },
  actions: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: 12,
    marginTop: 8,
  },
  secondaryButton: {
    padding: '8px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
  },
  commitButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    color: tokens.colors.background,
    background: tokens.colors.accent,
    cursor: 'pointer',
  },
};
