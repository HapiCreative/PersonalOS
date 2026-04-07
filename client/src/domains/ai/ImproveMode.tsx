/**
 * Improve Mode — Section 5.5: improvement retrieval -> prioritized recommendations.
 * Surfaces stale, blocked, and inefficient items.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { llmApi } from '../../api/endpoints';
import type { AIModeResponse } from '../../types';

export function ImproveMode() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIModeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await llmApi.improve(query.trim());
      setResult(response);
    } catch (e: any) {
      setError(e.message || 'Failed to generate improvements');
    } finally {
      setLoading(false);
    }
  };

  const data = result?.response_data || {};
  const summary = data.summary as string || result?.response_text || '';
  const recommendations = (data.recommendations as Array<Record<string, string>>) || [];
  const quickWins = (data.quick_wins as string[]) || [];
  const itemsToArchive = (data.items_to_archive as Array<Record<string, string>>) || [];

  return (
    <div style={styles.container}>
      <div style={styles.inputArea}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
          }}
          placeholder="What would you like to improve? E.g., 'How can I be more productive with my current tasks?'"
          style={styles.textarea}
          rows={3}
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || loading}
          style={{ ...styles.submitButton, opacity: !query.trim() || loading ? 0.5 : 1 }}
        >
          {loading ? 'Analyzing...' : 'Improve'}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {result && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeader}>
            <span style={styles.resultLabel}>Improvement Analysis</span>
            <span style={styles.meta}>{result.duration_ms}ms</span>
          </div>

          {summary && <p style={styles.summary}>{summary}</p>}

          {quickWins.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Quick Wins</h3>
              {quickWins.map((w, i) => (
                <div key={i} style={styles.quickWinItem}>{w}</div>
              ))}
            </div>
          )}

          {recommendations.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Recommendations</h3>
              {recommendations.map((r, i) => (
                <div key={i} style={styles.recCard}>
                  <div style={styles.recHeader}>
                    <span style={styles.recTitle}>{r.title}</span>
                    {r.priority && (
                      <span style={{
                        ...styles.priorityChip,
                        color: r.priority === 'high' ? tokens.colors.error : tokens.colors.textMuted,
                      }}>
                        {r.priority}
                      </span>
                    )}
                  </div>
                  {r.description && (
                    <span style={styles.recDesc}>{r.description}</span>
                  )}
                  {r.category && (
                    <span style={styles.categoryChip}>{r.category}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {itemsToArchive.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Consider Archiving</h3>
              {itemsToArchive.map((item, i) => (
                <div key={i} style={styles.archiveItem}>
                  <span style={styles.archiveTitle}>{item.title}</span>
                  <span style={styles.archiveReason}>{item.reason}</span>
                </div>
              ))}
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
  summary: {
    fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text,
    lineHeight: 1.6, margin: '0 0 16px',
  },
  section: { marginBottom: 16 },
  sectionTitle: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 12, color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const, letterSpacing: '0.05em', margin: '0 0 8px',
  },
  quickWinItem: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    padding: '6px 10px', background: `${tokens.colors.success}08`, borderRadius: tokens.radius,
    borderLeft: `2px solid ${tokens.colors.success}`, marginBottom: 4,
  },
  recCard: {
    padding: '10px 12px', background: tokens.colors.background,
    borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, marginBottom: 6,
  },
  recHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  recTitle: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13, color: tokens.colors.text },
  recDesc: { fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.textMuted, display: 'block', marginTop: 4 },
  priorityChip: {
    fontFamily: tokens.fonts.mono, fontSize: 10, padding: '1px 6px', borderRadius: tokens.radius,
    background: `${tokens.colors.textMuted}15`,
  },
  categoryChip: {
    fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`, padding: '1px 6px', borderRadius: tokens.radius,
    display: 'inline-block', marginTop: 6,
  },
  archiveItem: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '8px 12px', background: `${tokens.colors.warning}08`, borderRadius: tokens.radius,
    marginBottom: 4,
  },
  archiveTitle: { fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text },
  archiveReason: { fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.textMuted },
};
