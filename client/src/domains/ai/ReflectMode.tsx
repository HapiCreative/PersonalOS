/**
 * Reflect Mode — Section 5.5: reflection retrieval -> narrative + patterns.
 * Output is Derived, user can promote to Core note/KB entry.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { llmApi } from '../../api/endpoints';
import type { AIModeResponse } from '../../types';

export function ReflectMode() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIModeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await llmApi.reflect(query.trim());
      setResult(response);
    } catch (e: any) {
      setError(e.message || 'Failed to generate reflection');
    } finally {
      setLoading(false);
    }
  };

  const data = result?.response_data || {};
  const narrative = data.narrative as string || result?.response_text || '';
  const patterns = (data.patterns as string[]) || [];
  const accomplishments = (data.accomplishments as string[]) || [];
  const growthAreas = (data.growth_areas as string[]) || [];
  const insight = data.insight as string || '';

  return (
    <div style={styles.container}>
      <div style={styles.inputArea}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
          }}
          placeholder="What would you like to reflect on? E.g., 'How has my productivity been this week?'"
          style={styles.textarea}
          rows={3}
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || loading}
          style={{ ...styles.submitButton, opacity: !query.trim() || loading ? 0.5 : 1 }}
        >
          {loading ? 'Reflecting...' : 'Reflect'}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {result && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeader}>
            <span style={styles.resultLabel}>Reflection</span>
            <span style={styles.meta}>{result.duration_ms}ms</span>
          </div>

          {narrative && (
            <div style={styles.narrative}>{narrative}</div>
          )}

          {patterns.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Patterns</h3>
              {patterns.map((p, i) => (
                <div key={i} style={styles.patternItem}>{p}</div>
              ))}
            </div>
          )}

          {accomplishments.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Accomplishments</h3>
              {accomplishments.map((a, i) => (
                <div key={i} style={styles.accomplishmentItem}>{a}</div>
              ))}
            </div>
          )}

          {growthAreas.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Growth Areas</h3>
              {growthAreas.map((g, i) => (
                <div key={i} style={styles.growthItem}>{g}</div>
              ))}
            </div>
          )}

          {insight && (
            <div style={styles.insightBox}>
              <span style={styles.insightLabel}>Key Insight</span>
              <p style={styles.insightText}>{insight}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: 24, maxWidth: 720 },
  inputArea: { display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 },
  textarea: {
    fontFamily: tokens.fonts.sans, fontSize: 14,
    background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius, color: tokens.colors.text, padding: '10px 12px',
    resize: 'vertical', outline: 'none',
  },
  submitButton: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13,
    padding: '8px 16px', background: tokens.colors.violet, color: '#fff',
    border: 'none', borderRadius: tokens.radius, cursor: 'pointer', alignSelf: 'flex-end',
  },
  error: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.error,
    padding: '8px 12px', background: `${tokens.colors.error}15`, borderRadius: tokens.radius, marginBottom: 12,
  },
  resultContainer: {
    background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius, padding: 16,
  },
  resultHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12,
  },
  resultLabel: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 14, color: tokens.colors.violet },
  meta: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  narrative: {
    fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text,
    lineHeight: 1.7, marginBottom: 16, whiteSpace: 'pre-wrap',
  },
  section: { marginBottom: 16 },
  sectionTitle: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 12, color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const, letterSpacing: '0.05em', margin: '0 0 8px',
  },
  patternItem: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    padding: '6px 10px', background: `${tokens.colors.violet}08`, borderRadius: tokens.radius,
    borderLeft: `2px solid ${tokens.colors.violet}`, marginBottom: 4,
  },
  accomplishmentItem: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    padding: '6px 10px', background: `${tokens.colors.success}08`, borderRadius: tokens.radius,
    borderLeft: `2px solid ${tokens.colors.success}`, marginBottom: 4,
  },
  growthItem: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    padding: '6px 10px', background: `${tokens.colors.warning}08`, borderRadius: tokens.radius,
    borderLeft: `2px solid ${tokens.colors.warning}`, marginBottom: 4,
  },
  insightBox: {
    padding: 16, background: `${tokens.colors.violet}10`,
    border: `1px solid ${tokens.colors.violet}30`, borderRadius: tokens.radius,
  },
  insightLabel: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 12,
    color: tokens.colors.violet, textTransform: 'uppercase' as const,
  },
  insightText: {
    fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text,
    lineHeight: 1.6, margin: '8px 0 0',
  },
};
