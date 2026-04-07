/**
 * Strategic Alignment (secondary analytics tab).
 * Section 4.7: Goal progress over time, drift score trends, plan vs actual.
 *
 * Tier B: Pre-aggregated rollups for 30d+.
 * Invariant D-04: All outputs classified as descriptive/correlational/recommendation.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { analyticsApi } from '../../api/endpoints';
import { AnalyticsInsight } from './AnalyticsInsight';
import type { StrategicAlignmentResponse, DailyRollupResponse, WeeklyRollupResponse } from '../../types';

type Period = '30d' | '90d' | '6mo' | '1y';

export function StrategicAlignment() {
  const [period, setPeriod] = useState<Period>('30d');
  const [data, setData] = useState<StrategicAlignmentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [computing, setComputing] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    analyticsApi.getStrategic(period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [period]);

  const handleComputeRollups = () => {
    setComputing(true);
    const days = period === '30d' ? 30 : period === '90d' ? 90 : period === '6mo' ? 180 : 365;
    analyticsApi.computeRollups(days)
      .then(() => analyticsApi.getStrategic(period))
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setComputing(false));
  };

  if (loading) {
    return <div style={styles.loading}>Loading strategic metrics...</div>;
  }

  if (error) {
    return <div style={styles.error}>{error}</div>;
  }

  if (!data) return null;

  const { tier_b } = data;
  const hasDailyData = tier_b.daily_rollups.length > 0;
  const hasWeeklyData = tier_b.weekly_rollups.length > 0;

  return (
    <div>
      {/* Period selector + compute button */}
      <div style={styles.toolbar}>
        <div style={styles.periodBar}>
          {(['30d', '90d', '6mo', '1y'] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              style={{
                ...styles.periodButton,
                background: period === p ? tokens.colors.accent : 'transparent',
                color: period === p ? tokens.colors.background : tokens.colors.textMuted,
              }}
            >
              {p}
            </button>
          ))}
        </div>
        <button
          onClick={handleComputeRollups}
          disabled={computing}
          style={styles.computeButton}
        >
          {computing ? 'Computing...' : 'Recompute Rollups'}
        </button>
      </div>

      {!hasDailyData && !hasWeeklyData ? (
        <div style={styles.empty}>
          <p>No rollup data available for this period.</p>
          <p style={{ fontSize: 12, color: tokens.colors.textMuted }}>
            Click "Recompute Rollups" to generate analytics data from your activity history.
          </p>
        </div>
      ) : (
        <>
          {/* Weekly summary cards */}
          {hasWeeklyData && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Weekly Trends</h3>
              <div style={styles.tableWrapper}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Week</th>
                      <th style={styles.th}>Completion</th>
                      <th style={styles.th}>Accuracy</th>
                      <th style={styles.th}>Focus</th>
                      <th style={styles.th}>Momentum</th>
                      <th style={styles.th}>Mood</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tier_b.weekly_rollups.map((w) => (
                      <tr key={w.week_start_date}>
                        <td style={styles.td}>{formatWeek(w.week_start_date)}</td>
                        <td style={styles.td}>{(w.completion_rate * 100).toFixed(0)}%</td>
                        <td style={styles.td}>{(w.planning_accuracy * 100).toFixed(0)}%</td>
                        <td style={styles.td}>{formatDuration(w.total_focus_time)}</td>
                        <td style={styles.td}>{w.momentum.toFixed(1)}</td>
                        <td style={styles.td}>{w.avg_mood !== null ? w.avg_mood.toFixed(1) : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Goal drift summary */}
          {hasWeeklyData && tier_b.weekly_rollups.length > 0 && (
            <GoalDriftSection weekly={tier_b.weekly_rollups[tier_b.weekly_rollups.length - 1]} />
          )}

          {/* Daily planning accuracy chart (text-based) */}
          {hasDailyData && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Daily Planning Accuracy</h3>
              <div style={styles.chartContainer}>
                {tier_b.daily_rollups.slice(-14).map((d) => (
                  <DailyBar key={d.date} rollup={d} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Insights (Invariant D-04) */}
      {data.insights.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Insights</h3>
          {data.insights.map((insight, i) => (
            <AnalyticsInsight key={i} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}

function GoalDriftSection({ weekly }: { weekly: WeeklyRollupResponse }) {
  if (!weekly.drift_summary || weekly.drift_summary.length === 0) return null;

  return (
    <div style={styles.section}>
      <h3 style={styles.sectionTitle}>Goal Drift Status</h3>
      <div style={styles.driftList}>
        {weekly.drift_summary.map((item) => (
          <div key={item.goal_id} style={styles.driftItem}>
            <div style={styles.driftBar}>
              <div
                style={{
                  ...styles.driftFill,
                  width: `${Math.min(item.drift_score * 100, 100)}%`,
                  background: item.drift_score > 0.6
                    ? tokens.colors.error
                    : item.drift_score > 0.3
                    ? tokens.colors.warning
                    : tokens.colors.success,
                }}
              />
            </div>
            <span style={styles.driftLabel}>
              {item.goal_id.slice(0, 8)}... drift: {(item.drift_score * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DailyBar({ rollup }: { rollup: DailyRollupResponse }) {
  const accuracy = rollup.planning_accuracy;
  const barHeight = Math.max(accuracy * 60, 2);

  return (
    <div style={styles.barContainer} title={`${rollup.date}: ${(accuracy * 100).toFixed(0)}% accuracy`}>
      <div
        style={{
          ...styles.bar,
          height: barHeight,
          background: accuracy >= 0.8
            ? tokens.colors.success
            : accuracy >= 0.5
            ? tokens.colors.accent
            : accuracy > 0
            ? tokens.colors.warning
            : tokens.colors.border,
        }}
      />
      <span style={styles.barLabel}>
        {new Date(rollup.date + 'T00:00:00').getDate()}
      </span>
    </div>
  );
}

function formatWeek(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00');
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function formatDuration(seconds: number): string {
  if (seconds === 0) return '0m';
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  periodBar: {
    display: 'flex',
    gap: 8,
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
  computeButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    fontWeight: 600,
    color: tokens.colors.text,
    marginBottom: 12,
  },
  tableWrapper: {
    overflowX: 'auto' as const,
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
  },
  th: {
    textAlign: 'left' as const,
    padding: '8px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
    color: tokens.colors.textMuted,
    fontWeight: 600,
    fontSize: 11,
    textTransform: 'uppercase' as const,
  },
  td: {
    padding: '8px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
    color: tokens.colors.text,
  },
  chartContainer: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: 4,
    height: 80,
    padding: '8px 0',
  },
  barContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    flex: 1,
    justifyContent: 'flex-end',
  },
  bar: {
    width: '100%',
    maxWidth: 20,
    borderRadius: '2px 2px 0 0',
    minHeight: 2,
  },
  barLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    color: tokens.colors.textMuted,
    marginTop: 4,
  },
  driftList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 8,
  },
  driftItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  driftBar: {
    width: 120,
    height: 6,
    background: tokens.colors.border,
    borderRadius: 3,
    overflow: 'hidden' as const,
  },
  driftFill: {
    height: '100%',
    borderRadius: 3,
    transition: 'width 0.3s ease',
  },
  driftLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
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
  empty: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
};
