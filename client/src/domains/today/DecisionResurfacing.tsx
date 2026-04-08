/**
 * Decision Resurfacing UI (Section 5.7 — Phase PB).
 *
 * Behavioral workflow that resurfaces past decisions for outcome evaluation.
 * - Decisions with review_at due (user-set override)
 * - Decisions with no outcome after 7d/30d/90d
 * - Runs as query at load time, not scheduler
 *
 * Invariant D-01: All items include DerivedExplanation.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { decisionResurfacingApi } from '../../api/endpoints';
import { DerivedExplanationDisplay } from '../../components/derived/DerivedExplanationDisplay';
import type { DecisionResurfacingResponse, ResurfacedDecisionResponse } from '../../types';

const REASON_LABELS: Record<string, string> = {
  review_due: 'Review Scheduled',
  no_outcome_7d: '7 days — no outcome',
  no_outcome_30d: '30 days — no outcome',
  no_outcome_90d: '90 days — no outcome',
};

const REASON_COLORS: Record<string, string> = {
  review_due: tokens.colors.accent,
  no_outcome_7d: tokens.colors.warning,
  no_outcome_30d: tokens.colors.warning,
  no_outcome_90d: tokens.colors.error,
};

interface DecisionResurfacingProps {
  onNavigate?: (nodeId: string) => void;
}

export function DecisionResurfacing({ onNavigate }: DecisionResurfacingProps) {
  const [data, setData] = useState<DecisionResurfacingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await decisionResurfacingApi.get(10);
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load decision resurfacing');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.loadingState}>Checking decisions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.container}>
        <div style={styles.errorState}>
          <span>{error}</span>
          <button onClick={fetchData} style={styles.retryButton}>Retry</button>
        </div>
      </div>
    );
  }

  if (!data || data.total_count === 0) {
    return null; // Don't show section if no decisions need resurfacing
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={styles.heading}>Decision Review</h3>
        <div style={styles.stats}>
          {data.review_due_count > 0 && (
            <span style={styles.statChip}>
              {data.review_due_count} review due
            </span>
          )}
          {data.no_outcome_count > 0 && (
            <span style={styles.statChipWarn}>
              {data.no_outcome_count} need outcome
            </span>
          )}
        </div>
      </div>

      <div style={styles.cardList}>
        {data.items.map((decision) => (
          <DecisionCard
            key={decision.node_id}
            decision={decision}
            expanded={expandedId === decision.node_id}
            onToggle={() =>
              setExpandedId(expandedId === decision.node_id ? null : decision.node_id)
            }
            onNavigate={onNavigate}
          />
        ))}
      </div>
    </div>
  );
}

function DecisionCard({
  decision,
  expanded,
  onToggle,
  onNavigate,
}: {
  decision: ResurfacedDecisionResponse;
  expanded: boolean;
  onToggle: () => void;
  onNavigate?: (nodeId: string) => void;
}) {
  const reasonColor = REASON_COLORS[decision.resurfacing_reason] || tokens.colors.warning;
  const reasonLabel = REASON_LABELS[decision.resurfacing_reason] || decision.resurfacing_reason;

  return (
    <div style={{ ...styles.card, borderLeftColor: reasonColor }}>
      <button onClick={onToggle} style={styles.cardButton}>
        <div style={styles.cardTop}>
          <span style={styles.cardTitle}>{decision.title}</span>
          <span
            style={{
              ...styles.reasonBadge,
              color: reasonColor,
              borderColor: `${reasonColor}60`,
            }}
          >
            {reasonLabel}
          </span>
        </div>
        <div style={styles.cardMeta}>
          <span style={styles.daysBadge}>{decision.days_since_creation}d ago</span>
          {decision.review_at && (
            <span style={styles.reviewDate}>Review: {decision.review_at}</span>
          )}
          {decision.tags.length > 0 && (
            <span style={styles.tags}>{decision.tags.join(', ')}</span>
          )}
        </div>
      </button>

      {expanded && (
        <div style={styles.expandedContent}>
          {decision.context && (
            <div style={styles.contextBlock}>
              <span style={styles.contextLabel}>Context</span>
              <p style={styles.contextText}>{decision.context}</p>
            </div>
          )}

          <div style={styles.contentPreview}>
            {decision.content.slice(0, 300)}
            {decision.content.length > 300 && '...'}
          </div>

          {/* Invariant D-01: DerivedExplanation */}
          <DerivedExplanationDisplay explanation={decision.explanation} />

          <div style={styles.outcomeRow}>
            <span style={styles.outcomeLabel}>
              {decision.has_outcome_edges ? 'Has linked outcomes' : 'No outcomes recorded yet'}
            </span>
            {onNavigate && (
              <button
                onClick={() => onNavigate(decision.node_id)}
                style={styles.viewButton}
              >
                View Decision
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    marginBottom: 20,
  },
  loadingState: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    padding: '12px 0',
  },
  errorState: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.error,
    padding: '12px 0',
  },
  retryButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    cursor: 'pointer',
    background: 'none',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.text,
    margin: 0,
  },
  stats: {
    display: 'flex',
    gap: 6,
  },
  statChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    padding: '1px 6px',
    border: `1px solid ${tokens.colors.accent}40`,
    borderRadius: tokens.radius,
  },
  statChipWarn: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.warning,
    padding: '1px 6px',
    border: `1px solid ${tokens.colors.warning}40`,
    borderRadius: tokens.radius,
  },
  cardList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  card: {
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    borderLeft: '3px solid',
    overflow: 'hidden',
    background: tokens.colors.surface,
  },
  cardButton: {
    width: '100%',
    padding: '10px 12px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  cardTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  cardTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    color: tokens.colors.text,
    flex: 1,
  },
  reasonBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    padding: '1px 6px',
    border: '1px solid',
    borderRadius: tokens.radius,
    flexShrink: 0,
  },
  cardMeta: {
    display: 'flex',
    gap: 8,
    alignItems: 'center',
  },
  daysBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  reviewDate: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
  },
  tags: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  expandedContent: {
    padding: '0 12px 12px',
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  contextBlock: {
    marginTop: 8,
    marginBottom: 8,
  },
  contextLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    textTransform: 'uppercase' as const,
    letterSpacing: 1,
  },
  contextText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    margin: '4px 0 0',
    fontStyle: 'italic',
  },
  contentPreview: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    marginBottom: 8,
    lineHeight: 1.5,
  },
  outcomeRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  outcomeLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  viewButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.accent}50`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
};
