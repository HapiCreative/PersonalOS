/**
 * Wellbeing Patterns (tertiary analytics overlay).
 * Section 4.7: Mood over time, mood vs productivity correlations, energy patterns.
 *
 * Tier B: Pre-aggregated rollups for 30d+.
 * Invariant D-04: All outputs classified.
 * The system must never say "X causes Y" — only "X correlates with Y."
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { analyticsApi } from '../../api/endpoints';
import { AnalyticsInsight } from './AnalyticsInsight';
import type { WellbeingPatternsResponse } from '../../types';

type Period = '30d' | '90d' | '6mo' | '1y';

export function WellbeingPatterns() {
  const [period, setPeriod] = useState<Period>('30d');
  const [data, setData] = useState<WellbeingPatternsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    analyticsApi.getWellbeing(period)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [period]);

  if (loading) {
    return <div style={styles.loading}>Loading wellbeing data...</div>;
  }

  if (error) {
    return <div style={styles.error}>{error}</div>;
  }

  if (!data) return null;

  const hasMoodData = data.mood_data.length > 0;

  return (
    <div>
      {/* Period selector */}
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

      {!hasMoodData ? (
        <div style={styles.empty}>
          <p>No mood data available for this period.</p>
          <p style={{ fontSize: 12, color: tokens.colors.textMuted }}>
            Record your mood in journal entries to see wellbeing patterns.
          </p>
        </div>
      ) : (
        <>
          {/* Mood timeline */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Mood Over Time</h3>
            <div style={styles.moodTimeline}>
              {data.mood_data.slice(-30).map((entry) => (
                <MoodDot key={entry.date} date={entry.date} score={entry.mood_score} />
              ))}
            </div>
            <div style={styles.moodLegend}>
              <span style={{ ...styles.legendItem, color: moodColor(5) }}>Great</span>
              <span style={{ ...styles.legendItem, color: moodColor(4) }}>Good</span>
              <span style={{ ...styles.legendItem, color: moodColor(3) }}>Neutral</span>
              <span style={{ ...styles.legendItem, color: moodColor(2) }}>Low</span>
              <span style={{ ...styles.legendItem, color: moodColor(1) }}>Bad</span>
            </div>
          </div>

          {/* Mood summary stats */}
          <div style={styles.section}>
            <h3 style={styles.sectionTitle}>Summary</h3>
            <div style={styles.statGrid}>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Average Mood</div>
                <div style={styles.statValue}>
                  {averageMood(data.mood_data).toFixed(1)}
                </div>
                <div style={styles.statSubtext}>
                  {moodLabel(averageMood(data.mood_data))}
                </div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Entries</div>
                <div style={styles.statValue}>{data.mood_data.length}</div>
                <div style={styles.statSubtext}>journal entries with mood</div>
              </div>
              <div style={styles.statCard}>
                <div style={styles.statLabel}>Best Day</div>
                <div style={styles.statValue}>
                  {bestMoodDay(data.mood_data)}
                </div>
                <div style={styles.statSubtext}>highest mood score</div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Insights (Invariant D-04) */}
      {data.insights.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Patterns</h3>
          {data.insights.map((insight, i) => (
            <AnalyticsInsight key={i} insight={insight} />
          ))}
        </div>
      )}
    </div>
  );
}

function MoodDot({ date, score }: { date: string; score: number }) {
  const size = 10;
  const color = moodColor(score);

  return (
    <div
      style={styles.dotContainer}
      title={`${date}: ${moodLabel(score)} (${score})`}
    >
      <div
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: color,
        }}
      />
      <span style={styles.dotDate}>
        {new Date(date + 'T00:00:00').getDate()}
      </span>
    </div>
  );
}

function moodColor(score: number): string {
  if (score >= 4.5) return tokens.colors.success;
  if (score >= 3.5) return tokens.colors.accent;
  if (score >= 2.5) return tokens.colors.textMuted;
  if (score >= 1.5) return tokens.colors.warning;
  return tokens.colors.error;
}

function moodLabel(score: number): string {
  if (score >= 4.5) return 'Great';
  if (score >= 3.5) return 'Good';
  if (score >= 2.5) return 'Neutral';
  if (score >= 1.5) return 'Low';
  return 'Bad';
}

function averageMood(data: { mood_score: number }[]): number {
  if (data.length === 0) return 0;
  return data.reduce((sum, d) => sum + d.mood_score, 0) / data.length;
}

function bestMoodDay(data: { date: string; mood_score: number }[]): string {
  if (data.length === 0) return '-';
  const best = data.reduce((a, b) => (a.mood_score > b.mood_score ? a : b));
  const d = new Date(best.date + 'T00:00:00');
  return `${d.getMonth() + 1}/${d.getDate()}`;
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
  moodTimeline: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    flexWrap: 'wrap' as const,
    padding: '12px 0',
  },
  moodLegend: {
    display: 'flex',
    gap: 16,
    marginTop: 8,
  },
  legendItem: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
  },
  dotContainer: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    gap: 4,
  },
  dotDate: {
    fontFamily: tokens.fonts.mono,
    fontSize: 8,
    color: tokens.colors.textMuted,
  },
  statGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
    gap: 12,
  },
  statCard: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '14px',
  },
  statLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    fontWeight: 600,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: 6,
  },
  statValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 20,
    color: tokens.colors.text,
    marginBottom: 2,
  },
  statSubtext: {
    fontFamily: tokens.fonts.sans,
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
