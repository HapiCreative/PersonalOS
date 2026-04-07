/**
 * Analytics Insight display component.
 * Invariant D-04: Analytics output classification.
 *
 * Three tiers displayed with appropriate labels:
 * - Descriptive (no label): raw facts
 * - Correlational ("Pattern detected"): both variables shown, never implies causation
 * - Recommendation ("Suggestion"): cites underlying correlation, dismissible
 *
 * All three tiers use the DerivedExplanation schema (D-01).
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import type { AnalyticsOutputResponse } from '../../types';

interface Props {
  insight: AnalyticsOutputResponse;
}

export function AnalyticsInsight({ insight }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  // Invariant D-04: Recommendation must be dismissible
  if (dismissed) return null;

  const { classification, label, explanation } = insight;

  return (
    <div style={{
      ...styles.container,
      borderLeftColor: classificationColor(classification),
    }}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          {/* Invariant D-04: Classification label */}
          {label && (
            <span style={{
              ...styles.badge,
              background: `${classificationColor(classification)}20`,
              color: classificationColor(classification),
            }}>
              {label}
            </span>
          )}
          <span style={styles.summary}>{explanation.summary}</span>
        </div>
        <div style={styles.headerRight}>
          {/* Invariant D-04: Recommendation must be dismissible */}
          {classification === 'recommendation' && (
            <button
              onClick={() => setDismissed(true)}
              style={styles.dismissButton}
              title="Dismiss this suggestion"
            >
              &times;
            </button>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            style={styles.expandButton}
          >
            {expanded ? 'Less' : 'Details'}
          </button>
        </div>
      </div>

      {/* Expanded: show DerivedExplanation factors (D-01) */}
      {expanded && (
        <div style={styles.factors}>
          {explanation.factors.map((factor, i) => (
            <div key={i} style={styles.factorRow}>
              <span style={styles.factorSignal}>{factor.signal}</span>
              <span style={styles.factorValue}>
                {typeof factor.value === 'number'
                  ? Number(factor.value).toFixed(3)
                  : String(factor.value)}
              </span>
              <div style={styles.weightBar}>
                <div
                  style={{
                    ...styles.weightFill,
                    width: `${factor.weight * 100}%`,
                  }}
                />
              </div>
              <span style={styles.factorWeight}>
                {(factor.weight * 100).toFixed(0)}%
              </span>
            </div>
          ))}
          {explanation.confidence !== undefined && explanation.confidence !== null && (
            <div style={styles.confidence}>
              Confidence: {(explanation.confidence * 100).toFixed(0)}%
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function classificationColor(classification: string): string {
  switch (classification) {
    case 'descriptive':
      return tokens.colors.textMuted;
    case 'correlational':
      return tokens.colors.violet;
    case 'recommendation':
      return tokens.colors.accent;
    default:
      return tokens.colors.textMuted;
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderLeft: '3px solid',
    borderRadius: tokens.radius,
    padding: '12px 14px',
    marginBottom: 10,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 12,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    flex: 1,
    flexWrap: 'wrap' as const,
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    flexShrink: 0,
  },
  badge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: tokens.radius,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    whiteSpace: 'nowrap' as const,
  },
  summary: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    lineHeight: 1.4,
  },
  dismissButton: {
    width: 20,
    height: 20,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: 'none',
    background: 'none',
    color: tokens.colors.textMuted,
    fontSize: 16,
    cursor: 'pointer',
    borderRadius: tokens.radius,
  },
  expandButton: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    padding: '3px 8px',
    borderRadius: tokens.radius,
    cursor: 'pointer',
  },
  factors: {
    marginTop: 10,
    paddingTop: 10,
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  factorRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '3px 0',
  },
  factorSignal: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    minWidth: 140,
  },
  factorValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.text,
    minWidth: 60,
    textAlign: 'right' as const,
  },
  weightBar: {
    width: 60,
    height: 4,
    background: tokens.colors.border,
    borderRadius: 2,
    overflow: 'hidden' as const,
  },
  weightFill: {
    height: '100%',
    background: tokens.colors.accent,
    borderRadius: 2,
  },
  factorWeight: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    minWidth: 30,
  },
  confidence: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    marginTop: 6,
  },
};
