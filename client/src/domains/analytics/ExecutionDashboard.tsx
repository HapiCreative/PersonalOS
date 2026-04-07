/**
 * Execution Dashboard (primary analytics view).
 * Section 4.7: Task completion rates, planning accuracy, focus time, streaks.
 *
 * Tier A: Live query for today/7d/14d.
 * Invariant D-04: All outputs classified as descriptive.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { analyticsApi } from '../../api/endpoints';
import { AnalyticsInsight } from './AnalyticsInsight';
import type { ExecutionDashboardResponse } from '../../types';

type Period = 'today' | '7d' | '14d';

export function ExecutionDashboard() {
  const [period, setPeriod] = useState<Period>('7d');
  const [data, setData] = useState<ExecutionDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    analyticsApi.getExecution(period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [period]);

  if (loading) {
    return <div style={styles.loading}>Loading execution metrics...</div>;
  }

  if (error) {
    return <div style={styles.error}>{error}</div>;
  }

  if (!data) return null;

  const { tier_a: metrics } = data;

  return (
    <div>
      {/* Period selector */}
      <div style={styles.periodBar}>
        {(['today', '7d', '14d'] as Period[]).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            style={{
              ...styles.periodButton,
              background: period === p ? tokens.colors.accent : 'transparent',
              color: period === p ? tokens.colors.background : tokens.colors.textMuted,
            }}
          >
            {p === 'today' ? 'Today' : p}
          </button>
        ))}
      </div>

      {/* Metric cards */}
      <div style={styles.grid}>
        <MetricCard
          label="Tasks Completed"
          value={metrics.tasks_completed}
          subtitle={`${metrics.tasks_planned} planned`}
        />
        <MetricCard
          label="Planning Accuracy"
          value={`${(metrics.planning_accuracy * 100).toFixed(0)}%`}
          subtitle={`${metrics.tasks_planned_completed} of ${metrics.tasks_planned} planned done`}
        />
        <MetricCard
          label="Focus Time"
          value={formatDuration(metrics.focus_seconds_total)}
          subtitle={`${metrics.focus_sessions_count} sessions`}
        />
        <MetricCard
          label="Current Streak"
          value={`${metrics.current_streak} days`}
          subtitle={metrics.current_streak > 0 ? 'Keep it going!' : 'Complete a task to start'}
          accent={metrics.current_streak >= 3}
        />
        <MetricCard
          label="Journal Entries"
          value={metrics.journal_entries}
          subtitle={metrics.avg_mood !== null ? `Avg mood: ${moodLabel(metrics.avg_mood)}` : 'No mood data'}
        />
      </div>

      {/* Insights (Invariant D-04) */}
      {data.insights.length > 0 && (
        <div style={styles.insightsSection}>
          <h3 style={styles.sectionTitle}>Insights</h3>
          {data.insights.map((insight, i) => (
            <AnalyticsInsight key={i} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  subtitle,
  accent = false,
}: {
  label: string;
  value: string | number;
  subtitle: string;
  accent?: boolean;
}) {
  return (
    <div style={styles.card}>
      <div style={styles.cardLabel}>{label}</div>
      <div style={{
        ...styles.cardValue,
        color: accent ? tokens.colors.accent : tokens.colors.text,
      }}>
        {value}
      </div>
      <div style={styles.cardSubtitle}>{subtitle}</div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds === 0) return '0m';
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function moodLabel(score: number): string {
  if (score >= 4.5) return 'Great';
  if (score >= 3.5) return 'Good';
  if (score >= 2.5) return 'Neutral';
  if (score >= 1.5) return 'Low';
  return 'Bad';
}

const styles: Record<string, React.CSSProperties> = {
  periodBar: {
    display: 'flex',
    gap: 8,
    marginBottom: 20,
  },
  periodButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
    gap: 12,
    marginBottom: 24,
  },
  card: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '16px',
  },
  cardLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    fontWeight: 600,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: 6,
  },
  cardValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 24,
    fontWeight: 400,
    color: tokens.colors.text,
    marginBottom: 4,
  },
  cardSubtitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  insightsSection: {
    marginTop: 8,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    fontWeight: 600,
    color: tokens.colors.text,
    marginBottom: 12,
  },
  loading: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
  error: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.error,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
};
