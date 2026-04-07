/**
 * Weekly review UI: summary view + guided workflow steps.
 * Section 5.5: Hybrid summary + guided workflow → weekly_snapshots.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { weeklyReviewApi } from '../../api/endpoints';
import type { WeeklyReviewSummaryResponse } from '../../types';

export function WeeklyReview() {
  const [summary, setSummary] = useState<WeeklyReviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'review' | 'evaluate' | 'adjust' | 'commit'>('review');
  const [focusAreas, setFocusAreas] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    weeklyReviewApi.get()
      .then((data) => {
        setSummary(data);
        if (data.existing_snapshot) {
          setFocusAreas(((data.existing_snapshot as any).focus_areas || []).join(', '));
          setNotes((data.existing_snapshot as any).notes || '');
        }
      })
      .catch((e) => setError(e.message || 'Failed to load weekly review'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!summary) return;
    setSaving(true);
    setError(null);
    try {
      await weeklyReviewApi.save({
        focus_areas: focusAreas.split(',').map((s) => s.trim()).filter(Boolean),
        notes: notes || undefined,
      });
      setSaved(true);
    } catch (e: any) {
      setError(e.message || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div style={styles.loading}>Loading weekly review...</div>;
  if (error && !summary) return <div style={styles.error}>{error}</div>;
  if (!summary) return null;

  const completionPct = Math.round(summary.completion_rate * 100);
  const focusHours = Math.round(summary.total_focus_time_seconds / 3600 * 10) / 10;

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Weekly Review</h2>
      <div style={styles.dateRange}>
        {summary.week_start} — {summary.week_end}
      </div>

      {error && <div style={styles.errorBanner}>{error}</div>}
      {saved && <div style={styles.successBanner}>Weekly snapshot saved!</div>}

      {/* Step indicators */}
      <div style={styles.steps}>
        {(['review', 'evaluate', 'adjust', 'commit'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStep(s)}
            style={{
              ...styles.stepButton,
              color: step === s ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: step === s ? tokens.colors.accent : 'transparent',
            }}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Step 1: Review - Summary of the week */}
      {step === 'review' && (
        <div style={styles.stepContent}>
          <div style={styles.statsRow}>
            <div style={styles.stat}>
              <span style={styles.statValue}>{summary.total_completed}</span>
              <span style={styles.statLabel}>Completed</span>
            </div>
            <div style={styles.stat}>
              <span style={styles.statValue}>{summary.total_planned}</span>
              <span style={styles.statLabel}>Planned</span>
            </div>
            <div style={styles.stat}>
              <span style={styles.statValue}>{completionPct}%</span>
              <span style={styles.statLabel}>Completion</span>
            </div>
            <div style={styles.stat}>
              <span style={styles.statValue}>{focusHours}h</span>
              <span style={styles.statLabel}>Focus Time</span>
            </div>
          </div>

          {summary.completed_tasks.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Completed Tasks ({summary.completed_tasks.length})</h3>
              {summary.completed_tasks.map((t) => (
                <div key={t.node_id} style={styles.taskItem}>
                  <span style={{ ...styles.taskIcon, color: tokens.colors.success }}>✓</span>
                  <span style={styles.taskTitle}>{t.title}</span>
                  {t.was_planned && <span style={styles.planned}>planned</span>}
                </div>
              ))}
            </div>
          )}

          {summary.planned_tasks.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Incomplete Planned Tasks ({summary.planned_tasks.length})</h3>
              {summary.planned_tasks.map((t) => (
                <div key={t.node_id} style={styles.taskItem}>
                  <span style={{ ...styles.taskIcon, color: tokens.colors.warning }}>○</span>
                  <span style={styles.taskTitle}>{t.title}</span>
                  <span style={{
                    ...styles.taskPriority,
                    color: t.priority === 'urgent' ? tokens.colors.error
                      : t.priority === 'high' ? tokens.colors.warning
                      : tokens.colors.textMuted,
                  }}>{t.priority}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Step 2: Evaluate - Goal assessment */}
      {step === 'evaluate' && (
        <div style={styles.stepContent}>
          {summary.stalled_goals.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Stalled Goals</h3>
              <p style={styles.hint}>These goals have low progress and no completed tasks this week.</p>
              {summary.stalled_goals.map((g) => (
                <div key={g.node_id} style={styles.goalItem}>
                  <div style={styles.goalTop}>
                    <span style={styles.goalTitle}>{g.title}</span>
                    <span style={{ ...styles.goalProgress, color: tokens.colors.warning }}>
                      {Math.round(g.progress * 100)}%
                    </span>
                  </div>
                  <div style={styles.goalMeta}>
                    <span style={styles.goalStat}>{g.linked_task_count} tasks linked</span>
                    <span style={styles.goalStat}>{g.completed_task_count} completed this week</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>All Active Goals ({summary.active_goals.length})</h3>
            {summary.active_goals.map((g) => (
              <div key={g.node_id} style={styles.goalItem}>
                <div style={styles.goalTop}>
                  <span style={styles.goalTitle}>{g.title}</span>
                  <span style={styles.goalProgress}>{Math.round(g.progress * 100)}%</span>
                </div>
                <div style={styles.progressBarContainer}>
                  <div style={{
                    ...styles.progressBarFill,
                    width: `${Math.round(g.progress * 100)}%`,
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Step 3: Adjust - Set priorities */}
      {step === 'adjust' && (
        <div style={styles.stepContent}>
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Focus Areas for Next Week</h3>
            <p style={styles.hint}>Comma-separated key areas of focus.</p>
            <input
              value={focusAreas}
              onChange={(e) => setFocusAreas(e.target.value)}
              style={styles.input}
              placeholder="e.g. Ship feature X, Review PRs, Exercise daily"
            />
          </div>
        </div>
      )}

      {/* Step 4: Commit - Save snapshot */}
      {step === 'commit' && (
        <div style={styles.stepContent}>
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Weekly Notes</h3>
            <p style={styles.hint}>Capture your reflections on the week.</p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              style={styles.textArea}
              rows={6}
              placeholder="What went well? What could improve? Key learnings?"
            />
          </div>

          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Focus Areas</h3>
            <div style={styles.tagRow}>
              {focusAreas.split(',').map((a, i) => a.trim()).filter(Boolean).map((area, i) => (
                <span key={i} style={styles.tag}>{area}</span>
              ))}
              {!focusAreas.trim() && <span style={styles.hint}>No focus areas set — go to Adjust step</span>}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            style={styles.saveButton}
          >
            {saving ? 'Saving...' : saved ? 'Update Snapshot' : 'Save Weekly Snapshot'}
          </button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 720, padding: '0 24px' },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 22,
    color: tokens.colors.text,
    marginBottom: 4,
  },
  dateRange: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.textMuted,
    marginBottom: 16,
  },
  loading: { padding: 24, color: tokens.colors.textMuted, fontFamily: tokens.fonts.sans, textAlign: 'center' as const },
  error: { padding: 24, color: tokens.colors.error, fontFamily: tokens.fonts.sans },
  errorBanner: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.error}15`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  successBanner: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.success}15`,
    borderRadius: tokens.radius,
    color: tokens.colors.success,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  steps: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
    marginBottom: 20,
  },
  stepButton: {
    padding: '10px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
  },
  stepContent: { marginTop: 8 },
  statsRow: {
    display: 'flex',
    gap: 16,
    marginBottom: 24,
    padding: '16px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  stat: { display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 },
  statValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 24,
    fontWeight: 600,
    color: tokens.colors.accent,
  },
  statLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    marginTop: 4,
  },
  section: { marginBottom: 20 },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  hint: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    marginBottom: 8,
  },
  taskItem: {
    display: 'flex',
    gap: 10,
    padding: '6px 0',
    alignItems: 'center',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  taskIcon: {
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
  planned: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    padding: '1px 6px',
    borderRadius: tokens.radius,
  },
  taskPriority: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
  },
  goalItem: {
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  goalTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  goalTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  goalProgress: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.accent,
    fontWeight: 600,
  },
  goalMeta: { display: 'flex', gap: 12 },
  goalStat: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  progressBarContainer: {
    width: '100%',
    height: 4,
    background: tokens.colors.border,
    borderRadius: 2,
    marginTop: 6,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 2,
    background: tokens.colors.accent,
    transition: 'width 0.3s ease',
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
  tagRow: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    padding: '2px 8px',
    borderRadius: tokens.radius,
  },
  saveButton: {
    padding: '10px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    marginTop: 12,
  },
};
