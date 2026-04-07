/**
 * DerivedExplanation display component (Section 4.11).
 * Shows summary + expandable factors for any Derived output.
 *
 * Invariant D-01: Every user-facing Derived output includes
 * a DerivedExplanation with summary and factors[].
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import type { DerivedExplanation } from '../../types';

interface DerivedExplanationDisplayProps {
  explanation: DerivedExplanation;
  compact?: boolean;
}

export function DerivedExplanationDisplay({ explanation, compact = false }: DerivedExplanationDisplayProps) {
  const [expanded, setExpanded] = useState(false);

  if (compact) {
    return (
      <span style={styles.compactSummary} title={explanation.summary}>
        {explanation.summary}
      </span>
    );
  }

  return (
    <div style={styles.container}>
      {/* Summary (always visible) */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={styles.summaryButton}
      >
        <span style={styles.summaryIcon}>{expanded ? '▾' : '▸'}</span>
        <span style={styles.summaryText}>{explanation.summary}</span>
        {explanation.confidence != null && (
          <span style={styles.confidenceBadge}>
            {Math.round(explanation.confidence * 100)}%
          </span>
        )}
      </button>

      {/* Expandable factors */}
      {expanded && (
        <div style={styles.factorsContainer}>
          {explanation.factors.map((factor, idx) => (
            <div key={idx} style={styles.factorRow}>
              <span style={styles.factorSignal}>{factor.signal}</span>
              <span style={styles.factorValue}>
                {typeof factor.value === 'number'
                  ? factor.value
                  : String(factor.value)}
              </span>
              <div style={styles.factorWeightBar}>
                <div
                  style={{
                    ...styles.factorWeightFill,
                    width: `${Math.round(factor.weight * 100)}%`,
                  }}
                />
              </div>
              <span style={styles.factorWeight}>
                {Math.round(factor.weight * 100)}%
              </span>
            </div>
          ))}
          {explanation.version && (
            <div style={styles.versionLabel}>v{explanation.version}</div>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    overflow: 'hidden',
  },
  summaryButton: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    width: '100%',
    padding: '6px 10px',
    background: `${tokens.colors.violet}08`,
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  summaryIcon: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
    flexShrink: 0,
    width: 12,
  },
  summaryText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    flex: 1,
  },
  compactSummary: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  confidenceBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
    padding: '1px 5px',
    border: `1px solid ${tokens.colors.violet}40`,
    borderRadius: tokens.radius,
    flexShrink: 0,
  },
  factorsContainer: {
    padding: '6px 10px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  factorRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  factorSignal: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    minWidth: 100,
  },
  factorValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.text,
    minWidth: 50,
    textAlign: 'right' as const,
  },
  factorWeightBar: {
    flex: 1,
    height: 3,
    background: tokens.colors.border,
    borderRadius: 2,
    overflow: 'hidden',
  },
  factorWeightFill: {
    height: '100%',
    background: tokens.colors.violet,
    borderRadius: 2,
  },
  factorWeight: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    minWidth: 30,
    textAlign: 'right' as const,
  },
  versionLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    textAlign: 'right' as const,
    marginTop: 2,
  },
};
