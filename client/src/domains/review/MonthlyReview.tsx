/**
 * Monthly review UI: strategic reflection view.
 * Section 5.5: Same pattern as weekly, scoped to strategic questions.
 * References the month's weekly snapshots.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { monthlyReviewApi } from '../../api/endpoints';
import type { MonthlyReviewSummaryResponse } from '../../types';

export function MonthlyReview() {
  const [summary, setSummary] = useState<MonthlyReviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focusAreas, setFocusAreas] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    monthlyReviewApi.get()
      .then((data) => {
        setSummary(data);
        if (data.existing_snapshot) {
          setFocusAreas(((data.existing_snapshot as any).focus_areas || []).join(', '));
          setNotes((data.existing_snapshot as any).notes || '');
        }
      })
      .catch((e) => setError(e.message || 'Failed to load monthly review'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!summary) return;
    setSaving(true);
    setError(null);
    try {
      await monthlyReviewApi.save({
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

  if (loading) return <div style={styles.loading}>Loading monthly review...</div>;
  if (error && !summary) return <div style={styles.error}>{error}</div>;
  if (!summary) return null;

  const focusHours = Math.round(summary.total_focus_time_seconds / 3600 * 10) / 10;

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Monthly Review</h2>
      <div style={styles.monthLabel}>{summary.month_name}</div>

      {error && <div style={styles.errorBanner}>{error}</div>}
      {saved && <div style={styles.successBanner}>Monthly snapshot saved!</div>}

      {/* Summary stats */}
      <div style={styles.statsRow}>
        <div style={styles.stat}>
          <span style={styles.statValue}>{summary.total_tasks_completed}</span>
          <span style={styles.statLabel}>Tasks Completed</span>
        </div>
        <div style={styles.stat}>
          <span style={styles.statValue}>{focusHours}h</span>
          <span style={styles.statLabel}>Focus Time</span>
        </div>
        <div style={styles.stat}>
          <span style={styles.statValue}>{summary.weekly_snapshots.length}</span>
          <span style={styles.statLabel}>Weekly Reviews</span>
        </div>
        <div style={styles.stat}>
          <span style={styles.statValue}>{summary.goals.length}</span>
          <span style={styles.statLabel}>Active Goals</span>
        </div>
      </div>

      {/* Weekly snapshots in this month */}
      {summary.weekly_snapshots.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Weekly Snapshots</h3>
          {summary.weekly_snapshots.map((w, i) => (
            <div key={i} style={styles.weekItem}>
              <div style={styles.weekHeader}>
                <span style={styles.weekDates}>{w.week_start} — {w.week_end}</span>
              </div>
              {w.focus_areas.length > 0 && (
                <div style={styles.tagRow}>
                  {w.focus_areas.map((a, j) => (
                    <span key={j} style={styles.tag}>{a}</span>
                  ))}
                </div>
              )}
              {w.notes && <p style={styles.weekNotes}>{w.notes}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Goal progress */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Goals</h3>
        {summary.goals.length === 0 && (
          <p style={styles.hint}>No active goals for this month.</p>
        )}
        {summary.goals.map((g) => (
          <div key={g.node_id} style={styles.goalItem}>
            <div style={styles.goalTop}>
              <span style={styles.goalTitle}>{g.title}</span>
              <span style={{
                ...styles.goalProgress,
                color: g.progress >= 0.7 ? tokens.colors.success
                  : g.progress >= 0.3 ? tokens.colors.accent
                  : tokens.colors.warning,
              }}>
                {Math.round(g.progress * 100)}%
              </span>
            </div>
            <div style={styles.progressBarContainer}>
              <div style={{
                ...styles.progressBarFill,
                width: `${Math.round(g.progress * 100)}%`,
                background: g.status === 'completed' ? tokens.colors.success : tokens.colors.accent,
              }} />
            </div>
            <div style={styles.goalMeta}>
              <span style={styles.goalStat}>{g.tasks_completed_this_month} tasks completed this month</span>
              <span style={{
                ...styles.goalStatus,
                color: g.status === 'completed' ? tokens.colors.success : tokens.colors.accent,
              }}>{g.status}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Strategic reflection */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Strategic Focus Areas</h3>
        <p style={styles.hint}>What are your strategic priorities for next month?</p>
        <input
          value={focusAreas}
          onChange={(e) => setFocusAreas(e.target.value)}
          style={styles.input}
          placeholder="e.g. Launch product, Build habits, Learn skill"
        />
      </div>

      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Monthly Reflection</h3>
        <p style={styles.hint}>What strategic adjustments should you make?</p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          style={styles.textArea}
          rows={6}
          placeholder="Strategic insights, course corrections, priorities for next month..."
        />
      </div>

      <button
        onClick={handleSave}
        disabled={saving}
        style={styles.saveButton}
      >
        {saving ? 'Saving...' : saved ? 'Update Snapshot' : 'Save Monthly Snapshot'}
      </button>
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
  monthLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    color: tokens.colors.accent,
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
  section: { marginBottom: 24 },
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
  weekItem: {
    padding: '10px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  weekHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  weekDates: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.text,
  },
  tagRow: { display: 'flex', gap: 6, flexWrap: 'wrap' as const, marginBottom: 6 },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    padding: '2px 8px',
    borderRadius: tokens.radius,
  },
  weekNotes: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap' as const,
  },
  goalItem: {
    padding: '10px 0',
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
    fontWeight: 600,
  },
  progressBarContainer: {
    width: '100%',
    height: 4,
    background: tokens.colors.border,
    borderRadius: 2,
    marginTop: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 0.3s ease',
  },
  goalMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  goalStat: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  goalStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'capitalize' as const,
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
    marginBottom: 24,
  },
};
