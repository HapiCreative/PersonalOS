/**
 * Plan Mode — Section 5.5: execution_qa retrieval -> suggested milestones/tasks.
 * Promotes to Core on user accept.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { llmApi } from '../../api/endpoints';
import type { AIModeResponse } from '../../types';

export function PlanMode() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIModeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await llmApi.plan(query.trim());
      setResult(response);
    } catch (e: any) {
      setError(e.message || 'Failed to generate plan');
    } finally {
      setLoading(false);
    }
  };

  const planData = result?.response_data || {};
  const milestones = (planData.milestones as Array<Record<string, string>>) || [];
  const tasks = (planData.tasks as Array<Record<string, string>>) || [];
  const recommendations = (planData.recommendations as string[]) || [];

  return (
    <div style={styles.container}>
      <div style={styles.inputArea}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
          }}
          placeholder="What do you want to plan? E.g., 'Help me break down my Q2 goals into tasks'"
          style={styles.textarea}
          rows={3}
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || loading}
          style={{ ...styles.submitButton, opacity: !query.trim() || loading ? 0.5 : 1 }}
        >
          {loading ? 'Planning...' : 'Plan'}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {result && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeader}>
            <span style={styles.resultLabel}>Plan</span>
            <span style={styles.meta}>{result.duration_ms}ms</span>
          </div>

          {planData.summary && (
            <p style={styles.summary}>{planData.summary as string}</p>
          )}

          {milestones.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Milestones</h3>
              {milestones.map((m, i) => (
                <div key={i} style={styles.milestoneCard}>
                  <span style={styles.milestoneTitle}>{m.title}</span>
                  {m.description && (
                    <span style={styles.milestoneDesc}>{m.description}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {tasks.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Suggested Tasks</h3>
              {tasks.map((t, i) => (
                <div key={i} style={styles.taskCard}>
                  <div style={styles.taskHeader}>
                    <span style={styles.taskTitle}>{t.title}</span>
                    {t.priority && (
                      <span style={{
                        ...styles.priorityChip,
                        color: t.priority === 'high' || t.priority === 'urgent' ? tokens.colors.error : tokens.colors.textMuted,
                      }}>
                        {t.priority}
                      </span>
                    )}
                  </div>
                  {t.due_suggestion && (
                    <span style={styles.dueSuggestion}>Due: {t.due_suggestion}</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {recommendations.length > 0 && (
            <div style={styles.section}>
              <h3 style={styles.sectionTitle}>Recommendations</h3>
              <ul style={styles.recList}>
                {recommendations.map((r, i) => (
                  <li key={i} style={styles.recItem}>{r}</li>
                ))}
              </ul>
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
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13, color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const, letterSpacing: '0.05em', margin: '0 0 8px',
  },
  milestoneCard: {
    display: 'flex', flexDirection: 'column', gap: 2, padding: '8px 12px',
    background: `${tokens.colors.violet}08`, borderRadius: tokens.radius,
    borderLeft: `3px solid ${tokens.colors.violet}`, marginBottom: 6,
  },
  milestoneTitle: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13, color: tokens.colors.text },
  milestoneDesc: { fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.textMuted },
  taskCard: {
    padding: '8px 12px', background: tokens.colors.background,
    borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, marginBottom: 4,
  },
  taskHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  taskTitle: { fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text },
  priorityChip: {
    fontFamily: tokens.fonts.mono, fontSize: 10, padding: '1px 6px', borderRadius: tokens.radius,
    background: `${tokens.colors.textMuted}15`,
  },
  dueSuggestion: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  recList: { margin: 0, paddingLeft: 20 },
  recItem: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text, lineHeight: 1.6,
  },
};
