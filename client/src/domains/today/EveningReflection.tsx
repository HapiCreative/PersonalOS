/**
 * Evening Reflection UI (Section 5.1 — Phase 7).
 * Reflect stage of the 4-stage daily cycle.
 *
 * Workflow:
 * 1. Compare daily_plan vs actual task completion
 *    (via task_execution_events + expected_for_date = daily_plans.date)
 * 2. Quick reflection prompts
 * 3. Output: feedback into journal + derived metrics + execution events
 *    for skipped/deferred tasks
 *
 * Invariant S-04: One terminal event per task per date.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { eveningReflectionApi } from '../../api/endpoints';
import type {
  EveningReflectionResponse,
  TaskReflectionItemResponse,
  ReflectionPromptResponse,
} from '../../types';

interface EveningReflectionProps {
  onComplete: () => void;
  onSkip: () => void;
}

export function EveningReflection({ onComplete, onSkip }: EveningReflectionProps) {
  const [data, setData] = useState<EveningReflectionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skippedIds, setSkippedIds] = useState<Set<string>>(new Set());
  const [deferredIds, setDeferredIds] = useState<Set<string>>(new Set());
  const [reflectionNotes, setReflectionNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await eveningReflectionApi.get();
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load reflection data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const markSkipped = (nodeId: string) => {
    setSkippedIds((prev) => {
      const next = new Set(prev);
      next.add(nodeId);
      setDeferredIds((d) => {
        const nd = new Set(d);
        nd.delete(nodeId);
        return nd;
      });
      return next;
    });
  };

  const markDeferred = (nodeId: string) => {
    setDeferredIds((prev) => {
      const next = new Set(prev);
      next.add(nodeId);
      setSkippedIds((s) => {
        const ns = new Set(s);
        ns.delete(nodeId);
        return ns;
      });
      return next;
    });
  };

  const clearMark = (nodeId: string) => {
    setSkippedIds((prev) => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
    setDeferredIds((prev) => {
      const next = new Set(prev);
      next.delete(nodeId);
      return next;
    });
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await eveningReflectionApi.submit({
        skipped_task_ids: Array.from(skippedIds),
        deferred_task_ids: Array.from(deferredIds),
        reflection_notes: reflectionNotes || undefined,
      });
      onComplete();
    } catch (e: any) {
      setError(e.message || 'Failed to submit reflection');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingState}>Loading reflection data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.errorState}>
          <p>{error}</p>
          <button onClick={fetchData} style={styles.secondaryButton}>Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const completionPercent = Math.round(data.completion_rate * 100);
  const focusMinutes = Math.round(data.total_focus_time_seconds / 60);

  // Find incomplete planned tasks (no event yet)
  const incompletePlanned = data.planned_tasks.filter(
    (t) => !t.event_type && t.status !== 'done' && t.status !== 'cancelled',
  );

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        {/* Header */}
        <div style={styles.header}>
          <h2 style={styles.heading}>Evening Reflection</h2>
          <p style={styles.subtitle}>
            {new Date(data.date).toLocaleDateString('en-US', {
              weekday: 'long', month: 'long', day: 'numeric',
            })}
          </p>
        </div>

        {/* Stats summary */}
        <div style={styles.statsRow}>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{completionPercent}%</div>
            <div style={styles.statLabel}>Completion</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{data.total_completed}</div>
            <div style={styles.statLabel}>Completed</div>
          </div>
          <div style={styles.statCard}>
            <div style={styles.statValue}>{focusMinutes}m</div>
            <div style={styles.statLabel}>Focus Time</div>
          </div>
        </div>

        {data.intention_text && (
          <div style={styles.intentionCard}>
            <div style={styles.intentionLabel}>Today's Intention</div>
            <p style={styles.intentionText}>"{data.intention_text}"</p>
          </div>
        )}

        {/* Plan vs Actual */}
        {data.plan_exists && data.planned_tasks.length > 0 && (
          <div style={styles.sectionCard}>
            <div style={styles.sectionHeader}>
              <span style={styles.sectionTitle}>Plan vs Actual</span>
              <span style={styles.sectionMeta}>
                {data.total_planned} planned
              </span>
            </div>
            <div style={styles.taskList}>
              {data.planned_tasks.map((task) => (
                <PlannedTaskRow key={task.node_id} task={task} />
              ))}
            </div>
          </div>
        )}

        {/* Unplanned completions */}
        {data.unplanned_completed.length > 0 && (
          <div style={styles.sectionCard}>
            <div style={styles.sectionHeader}>
              <span style={styles.sectionTitle}>Bonus Completions</span>
              <span style={styles.sectionMeta}>
                {data.unplanned_completed.length} extra
              </span>
            </div>
            <div style={styles.taskList}>
              {data.unplanned_completed.map((task) => (
                <PlannedTaskRow key={task.node_id} task={task} />
              ))}
            </div>
          </div>
        )}

        {/* Incomplete tasks — mark as skipped or deferred */}
        {incompletePlanned.length > 0 && (
          <div style={styles.sectionCard}>
            <div style={styles.sectionHeader}>
              <span style={styles.sectionTitle}>Incomplete Tasks</span>
              <span style={styles.sectionMeta}>
                Mark as skipped or deferred
              </span>
            </div>
            <div style={styles.taskList}>
              {incompletePlanned.map((task) => {
                const isSkipped = skippedIds.has(task.node_id);
                const isDeferred = deferredIds.has(task.node_id);
                return (
                  <div key={task.node_id} style={styles.incompleteRow}>
                    <div style={styles.taskInfo}>
                      <span style={styles.taskTitle}>{task.title}</span>
                      <span style={styles.taskMeta}>
                        {task.priority} &middot; {task.status}
                      </span>
                    </div>
                    <div style={styles.markActions}>
                      <button
                        onClick={() => isSkipped ? clearMark(task.node_id) : markSkipped(task.node_id)}
                        style={{
                          ...styles.markButton,
                          color: isSkipped ? tokens.colors.error : tokens.colors.textMuted,
                          borderColor: isSkipped ? tokens.colors.error : tokens.colors.border,
                        }}
                      >
                        Skip
                      </button>
                      <button
                        onClick={() => isDeferred ? clearMark(task.node_id) : markDeferred(task.node_id)}
                        style={{
                          ...styles.markButton,
                          color: isDeferred ? tokens.colors.warning : tokens.colors.textMuted,
                          borderColor: isDeferred ? tokens.colors.warning : tokens.colors.border,
                        }}
                      >
                        Defer
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Reflection prompts */}
        <div style={styles.sectionCard}>
          <div style={styles.sectionHeader}>
            <span style={styles.sectionTitle}>Reflect</span>
          </div>
          <div style={styles.promptsList}>
            {data.prompts.map((prompt) => (
              <div key={prompt.prompt_id} style={styles.promptItem}>
                <span style={styles.promptText}>{prompt.text}</span>
              </div>
            ))}
          </div>
          <textarea
            value={reflectionNotes}
            onChange={(e) => setReflectionNotes(e.target.value)}
            placeholder="Write your reflection here... (optional)"
            style={styles.reflectionInput}
            rows={4}
          />
        </div>

        {/* Actions */}
        <div style={styles.actions}>
          <button onClick={onSkip} style={styles.secondaryButton}>
            Skip reflection
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              ...styles.submitButton,
              opacity: submitting ? 0.5 : 1,
            }}
          >
            {submitting ? 'Submitting...' : 'Complete Reflection'}
          </button>
        </div>
      </div>
    </div>
  );
}

function PlannedTaskRow({ task }: { task: TaskReflectionItemResponse }) {
  const isCompleted = task.event_type === 'completed' || task.status === 'done';
  const isSkipped = task.event_type === 'skipped';
  const isDeferred = task.event_type === 'deferred';
  const focusMin = Math.round(task.focus_time_seconds / 60);

  return (
    <div style={styles.taskRow}>
      <div style={{
        ...styles.statusDot,
        background: isCompleted ? tokens.colors.success
          : isSkipped ? tokens.colors.error
          : isDeferred ? tokens.colors.warning
          : tokens.colors.textMuted,
      }} />
      <div style={styles.taskInfo}>
        <span style={{
          ...styles.taskTitle,
          textDecoration: isCompleted ? 'line-through' : 'none',
          color: isCompleted ? tokens.colors.textMuted : tokens.colors.text,
        }}>
          {task.title}
        </span>
        <div style={styles.taskMetaRow}>
          <span style={styles.taskMeta}>{task.priority}</span>
          {task.event_type && (
            <span style={{
              ...styles.eventBadge,
              color: isCompleted ? tokens.colors.success
                : isSkipped ? tokens.colors.error
                : tokens.colors.warning,
            }}>
              {task.event_type}
            </span>
          )}
          {focusMin > 0 && (
            <span style={styles.focusTimeBadge}>{focusMin}m focus</span>
          )}
          {!task.was_planned && (
            <span style={styles.bonusBadge}>bonus</span>
          )}
        </div>
      </div>
    </div>
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
    marginBottom: 20,
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
  statsRow: {
    display: 'flex',
    gap: 12,
    marginBottom: 20,
  },
  statCard: {
    flex: 1,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '14px 12px',
    textAlign: 'center' as const,
  },
  statValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 24,
    fontWeight: 600,
    color: tokens.colors.accent,
    marginBottom: 4,
  },
  statLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
  },
  intentionCard: {
    background: `${tokens.colors.violet}08`,
    border: `1px solid ${tokens.colors.violet}30`,
    borderRadius: tokens.radius,
    padding: '12px 14px',
    marginBottom: 20,
  },
  intentionLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.violet,
    textTransform: 'uppercase' as const,
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  intentionText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
    fontStyle: 'italic',
    margin: 0,
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
  sectionMeta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
  },
  taskRow: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 10,
    padding: '10px 14px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
    marginTop: 5,
  },
  taskInfo: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    gap: 3,
  },
  taskTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  taskMetaRow: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    flexWrap: 'wrap',
  },
  taskMeta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  eventBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    padding: '1px 5px',
    borderRadius: tokens.radius,
  },
  focusTimeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    padding: '1px 5px',
    background: `${tokens.colors.accent}15`,
    borderRadius: tokens.radius,
  },
  bonusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.success,
    padding: '1px 5px',
    background: `${tokens.colors.success}15`,
    borderRadius: tokens.radius,
  },
  incompleteRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  markActions: {
    display: 'flex',
    gap: 6,
    flexShrink: 0,
  },
  markButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: '1px solid',
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    cursor: 'pointer',
    background: 'none',
  },
  promptsList: {
    padding: '10px 14px 0',
  },
  promptItem: {
    padding: '6px 0',
  },
  promptText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    lineHeight: 1.5,
  },
  reflectionInput: {
    width: '100%',
    padding: '10px 14px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    background: tokens.colors.background,
    border: 'none',
    borderTop: `1px solid ${tokens.colors.border}`,
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
  submitButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    color: tokens.colors.background,
    background: tokens.colors.violet,
    cursor: 'pointer',
  },
};
