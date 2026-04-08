/**
 * Focus Mode UI (Section 5.1 — Phase 7 + Phase PB enhancements).
 * Execute stage of the 4-stage daily cycle.
 *
 * Shows only selected priorities from daily plan.
 * Optional timer + session tracking -> focus_sessions record.
 *
 * Phase PB enhancements:
 * - Session tracking: history of focus sessions with stats
 * - Contextual scoping: related context for the focused task
 *
 * Invariant T-02: Focus sessions are append-only (no deletes).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { tokens } from '../../styles/tokens';
import { focusSessionsApi, dailyPlansApi, focusStatsApi, derivedApi } from '../../api/endpoints';
import type {
  DailyPlanResponse,
  FocusSessionResponse,
  TaskResponse,
  FocusStatsResponse,
  ContextLayerResponse,
} from '../../types';
import { tasksApi } from '../../api/endpoints';

interface FocusModeProps {
  onExit: () => void;
}

export function FocusMode({ onExit }: FocusModeProps) {
  const [plan, setPlan] = useState<DailyPlanResponse | null>(null);
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [activeSession, setActiveSession] = useState<FocusSessionResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [loading, setLoading] = useState(true);
  // Phase PB: Focus stats and context
  const [stats, setStats] = useState<FocusStatsResponse | null>(null);
  const [context, setContext] = useState<ContextLayerResponse | null>(null);
  const [showStats, setShowStats] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [planResult, sessionResult] = await Promise.all([
        dailyPlansApi.getToday(),
        focusSessionsApi.getActive(),
      ]);
      setPlan(planResult);
      setActiveSession(sessionResult);

      // Fetch task details for planned tasks
      if (planResult?.selected_task_ids?.length) {
        const taskPromises = planResult.selected_task_ids.map((id) =>
          tasksApi.get(id).catch(() => null),
        );
        const results = await Promise.all(taskPromises);
        setTasks(results.filter(Boolean) as TaskResponse[]);
      }

      // If there's an active session, compute elapsed time
      if (sessionResult && !sessionResult.ended_at) {
        const start = new Date(sessionResult.started_at).getTime();
        setElapsed(Math.floor((Date.now() - start) / 1000));
      }

      // Phase PB: Fetch focus stats
      try {
        const statsResult = await focusStatsApi.getStats({ days: 7 });
        setStats(statsResult);
      } catch {
        // Stats are optional
      }
    } catch {
      // Silently fail — will show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Timer tick
  useEffect(() => {
    if (activeSession && !activeSession.ended_at) {
      timerRef.current = setInterval(() => {
        const start = new Date(activeSession.started_at).getTime();
        setElapsed(Math.floor((Date.now() - start) / 1000));
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [activeSession]);

  // Phase PB: Fetch context for active task
  useEffect(() => {
    const taskId = activeSession?.task_id;
    if (taskId && showContext) {
      derivedApi.getContextLayer(taskId)
        .then(setContext)
        .catch(() => setContext(null));
    }
  }, [activeSession?.task_id, showContext]);

  const startSession = async (taskId: string) => {
    try {
      const session = await focusSessionsApi.start(taskId);
      setActiveSession(session);
      setElapsed(0);
    } catch (e: any) {
      console.error('Failed to start focus session:', e);
    }
  };

  const endSession = async () => {
    if (!activeSession) return;
    try {
      await focusSessionsApi.end(activeSession.id);
      setActiveSession(null);
      setElapsed(0);
      setContext(null);
      if (timerRef.current) clearInterval(timerRef.current);
      fetchData();
    } catch (e: any) {
      console.error('Failed to end focus session:', e);
    }
  };

  const formatTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingState}>Entering focus mode...</div>
      </div>
    );
  }

  const activeTaskId = activeSession?.task_id;

  return (
    <div style={styles.container}>
      <div style={styles.inner}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerRow}>
            <h2 style={styles.heading}>Focus Mode</h2>
            <div style={styles.headerActions}>
              <button
                onClick={() => setShowStats(!showStats)}
                style={{
                  ...styles.toggleButton,
                  ...(showStats ? styles.toggleButtonActive : {}),
                }}
              >
                Stats
              </button>
              <button onClick={onExit} style={styles.exitButton}>
                Exit Focus
              </button>
            </div>
          </div>
          {plan?.intention_text && (
            <p style={styles.intention}>"{plan.intention_text}"</p>
          )}
        </div>

        {/* Active timer */}
        {activeSession && !activeSession.ended_at && (
          <div style={styles.timerCard}>
            <div style={styles.timerLabel}>Focusing on</div>
            <div style={styles.timerTaskTitle}>
              {tasks.find((t) => t.node_id === activeTaskId)?.title || 'Task'}
            </div>
            <div style={styles.timerDisplay}>{formatTime(elapsed)}</div>
            <div style={styles.timerActions}>
              <button onClick={endSession} style={styles.stopButton}>
                Stop Session
              </button>
              <button
                onClick={() => setShowContext(!showContext)}
                style={{
                  ...styles.contextToggle,
                  ...(showContext ? styles.contextToggleActive : {}),
                }}
              >
                {showContext ? 'Hide Context' : 'Show Context'}
              </button>
            </div>
          </div>
        )}

        {/* Phase PB: Contextual scoping — show related context for focused task */}
        {showContext && context && context.total_count > 0 && (
          <div style={styles.contextSection}>
            <div style={styles.contextSectionTitle}>Related Context</div>
            {context.categories.map((cat) => (
              <div key={cat.name} style={styles.contextCategory}>
                <div style={styles.contextCatLabel}>{cat.name.replace(/_/g, ' ')}</div>
                {cat.items.map((item, idx) => (
                  <div key={`${item.node_id}-${idx}`} style={styles.contextItem}>
                    <span style={styles.contextItemType}>{item.node_type}</span>
                    <span style={styles.contextItemTitle}>{item.title}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Phase PB: Focus session stats */}
        {showStats && stats && (
          <div style={styles.statsSection}>
            <div style={styles.statsTitle}>Last 7 Days</div>
            <div style={styles.statsGrid}>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{stats.total_sessions}</span>
                <span style={styles.statLabel}>Sessions</span>
              </div>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{formatDuration(stats.total_seconds)}</span>
                <span style={styles.statLabel}>Total Time</span>
              </div>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{formatDuration(stats.avg_session_seconds)}</span>
                <span style={styles.statLabel}>Avg Session</span>
              </div>
              <div style={styles.statCard}>
                <span style={styles.statValue}>{formatDuration(stats.longest_session_seconds)}</span>
                <span style={styles.statLabel}>Longest</span>
              </div>
            </div>
            {stats.task_breakdown.length > 0 && (
              <div style={styles.taskBreakdown}>
                <div style={styles.breakdownTitle}>By Task</div>
                {stats.task_breakdown.map((tb) => (
                  <div key={tb.task_id} style={styles.breakdownRow}>
                    <span style={styles.breakdownTask}>{tb.title}</span>
                    <span style={styles.breakdownTime}>
                      {tb.sessions}x &middot; {formatDuration(tb.total_seconds)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Task list — minimal, focused */}
        <div style={styles.taskSection}>
          <div style={styles.sectionTitle}>
            {plan ? 'Committed Priorities' : 'In Progress Tasks'}
          </div>

          {tasks.length === 0 ? (
            <div style={styles.emptyState}>
              <p style={styles.emptyText}>
                {plan ? 'No tasks in today\'s plan.' : 'No tasks to focus on. Commit a morning plan first.'}
              </p>
            </div>
          ) : (
            <div style={styles.taskList}>
              {tasks.map((task) => {
                const isActive = activeTaskId === task.node_id;
                const isDone = task.status === 'done' || task.status === 'cancelled';

                return (
                  <div
                    key={task.node_id}
                    style={{
                      ...styles.taskCard,
                      borderLeftColor: isActive
                        ? tokens.colors.accent
                        : isDone
                        ? tokens.colors.success
                        : tokens.colors.border,
                      opacity: isDone ? 0.6 : 1,
                    }}
                  >
                    <div style={styles.taskInfo}>
                      <span style={{
                        ...styles.taskTitle,
                        textDecoration: isDone ? 'line-through' : 'none',
                      }}>
                        {task.title}
                      </span>
                      <span style={styles.taskMeta}>
                        {task.priority} &middot; {task.status}
                        {task.due_date && ` \u00b7 Due ${task.due_date}`}
                      </span>
                    </div>
                    {!isDone && (
                      <div style={styles.taskActions}>
                        {isActive ? (
                          <button onClick={endSession} style={styles.actionButtonActive}>
                            Stop
                          </button>
                        ) : (
                          <button
                            onClick={() => startSession(task.node_id)}
                            style={styles.actionButton}
                            disabled={!!activeSession && !activeSession.ended_at}
                          >
                            Focus
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
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
    maxWidth: 520,
    margin: '0 auto',
    padding: '32px 20px',
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
  header: {
    marginBottom: 28,
  },
  headerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
    margin: 0,
  },
  headerActions: {
    display: 'flex',
    gap: 6,
  },
  toggleButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
  },
  toggleButtonActive: {
    color: tokens.colors.accent,
    borderColor: tokens.colors.accent,
    background: `${tokens.colors.accent}10`,
  },
  exitButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
  },
  intention: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    fontStyle: 'italic',
    margin: 0,
  },
  timerCard: {
    background: `${tokens.colors.accent}08`,
    border: `1px solid ${tokens.colors.accent}30`,
    borderRadius: tokens.radius,
    padding: '20px',
    textAlign: 'center' as const,
    marginBottom: 24,
  },
  timerLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
    marginBottom: 6,
  },
  timerTaskTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 16,
    fontWeight: 600,
    color: tokens.colors.text,
    marginBottom: 12,
  },
  timerDisplay: {
    fontFamily: tokens.fonts.mono,
    fontSize: 48,
    fontWeight: 600,
    color: tokens.colors.accent,
    marginBottom: 16,
    letterSpacing: 2,
  },
  timerActions: {
    display: 'flex',
    justifyContent: 'center',
    gap: 10,
  },
  stopButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.error}50`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.error,
    cursor: 'pointer',
    background: 'none',
  },
  contextToggle: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
  },
  contextToggleActive: {
    color: tokens.colors.violet,
    borderColor: tokens.colors.violet,
    background: `${tokens.colors.violet}10`,
  },
  // Phase PB: Context section
  contextSection: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    marginBottom: 16,
    padding: '12px',
  },
  contextSectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.violet,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: 8,
  },
  contextCategory: {
    marginBottom: 6,
  },
  contextCatLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    textTransform: 'capitalize' as const,
    marginBottom: 3,
  },
  contextItem: {
    display: 'flex',
    gap: 6,
    padding: '3px 0',
    marginLeft: 8,
  },
  contextItemType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.textMuted,
    padding: '0 4px',
    background: `${tokens.colors.textMuted}15`,
    borderRadius: '2px',
    flexShrink: 0,
  },
  contextItemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  // Phase PB: Stats section
  statsSection: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    marginBottom: 16,
    padding: '12px',
  },
  statsTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.text,
    marginBottom: 10,
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr 1fr 1fr',
    gap: 8,
    marginBottom: 12,
  },
  statCard: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 2,
    padding: '8px 4px',
    background: tokens.colors.background,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
  },
  statValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    fontWeight: 600,
    color: tokens.colors.accent,
  },
  statLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
  },
  taskBreakdown: {
    borderTop: `1px solid ${tokens.colors.border}`,
    paddingTop: 8,
  },
  breakdownTitle: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    marginBottom: 6,
    textTransform: 'uppercase' as const,
  },
  breakdownRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '3px 0',
  },
  breakdownTask: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  breakdownTime: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    flexShrink: 0,
    marginLeft: 8,
  },
  taskSection: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    overflow: 'hidden',
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.text,
    padding: '10px 14px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  emptyState: {
    padding: '24px 14px',
    textAlign: 'center' as const,
  },
  emptyText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    margin: 0,
  },
  taskList: {
    display: 'flex',
    flexDirection: 'column',
  },
  taskCard: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '10px 14px',
    borderLeft: '3px solid',
    borderBottom: `1px solid ${tokens.colors.border}`,
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
  taskMeta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  taskActions: {
    flexShrink: 0,
    marginLeft: 12,
  },
  actionButton: {
    padding: '5px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.accent}50`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  actionButtonActive: {
    padding: '5px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.error}50`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.error,
    cursor: 'pointer',
    background: 'none',
  },
};
