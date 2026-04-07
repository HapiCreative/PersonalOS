/**
 * Ask Mode — Section 5.5: Factual Q&A with citations.
 * factual_qa retrieval -> answer + citations -> ai_interaction_logs.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { llmApi } from '../../api/endpoints';
import type { AIModeResponse } from '../../types';

export function AskMode() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIModeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<AIModeResponse[]>([]);

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await llmApi.ask(query.trim());
      setResult(response);
      setHistory((prev) => [response, ...prev]);
      setQuery('');
    } catch (e: any) {
      setError(e.message || 'Failed to get answer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.inputArea}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          placeholder="Ask a question about your knowledge base..."
          style={styles.textarea}
          rows={3}
        />
        <button
          onClick={handleSubmit}
          disabled={!query.trim() || loading}
          style={{
            ...styles.submitButton,
            opacity: !query.trim() || loading ? 0.5 : 1,
          }}
        >
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {result && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeader}>
            <span style={styles.resultLabel}>Answer</span>
            <span style={styles.meta}>
              {result.duration_ms}ms | {result.model_version}
            </span>
          </div>
          <div style={styles.resultText}>{result.response_text}</div>

          {result.citations.length > 0 && (
            <div style={styles.citationsSection}>
              <span style={styles.citationsLabel}>Citations</span>
              <div style={styles.citationsList}>
                {result.citations.map((c, i) => (
                  <div key={i} style={styles.citation}>
                    <span style={styles.citationType}>{c.node_type}</span>
                    <span style={styles.citationTitle}>{c.title}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.context_items.length > 0 && (
            <div style={styles.contextSection}>
              <span style={styles.citationsLabel}>
                Context ({result.context_items.length} items)
              </span>
              <div style={styles.citationsList}>
                {result.context_items.map((item, i) => (
                  <div key={i} style={styles.contextItem}>
                    <span style={styles.citationType}>{item.node_type}</span>
                    <span style={styles.citationTitle}>{item.title}</span>
                    <span style={styles.scoreChip}>
                      {(item.combined_score * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {history.length > 1 && (
        <div style={styles.historySection}>
          <span style={styles.historyLabel}>Previous Questions</span>
          {history.slice(1, 6).map((h, i) => (
            <div key={i} style={styles.historyItem}>
              <span style={styles.historyQuery}>{h.query}</span>
              <span style={styles.meta}>{h.duration_ms}ms</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: 24, maxWidth: 720 },
  inputArea: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    marginBottom: 16,
  },
  textarea: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    padding: '10px 12px',
    resize: 'vertical',
    outline: 'none',
  },
  submitButton: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    padding: '8px 16px',
    background: tokens.colors.violet,
    color: '#fff',
    border: 'none',
    borderRadius: tokens.radius,
    cursor: 'pointer',
    alignSelf: 'flex-end',
  },
  error: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.error,
    padding: '8px 12px',
    background: `${tokens.colors.error}15`,
    borderRadius: tokens.radius,
    marginBottom: 12,
  },
  resultContainer: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: 16,
    marginBottom: 16,
  },
  resultHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  resultLabel: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.violet,
  },
  meta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  resultText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
  },
  citationsSection: { marginTop: 16, paddingTop: 12, borderTop: `1px solid ${tokens.colors.border}` },
  citationsLabel: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  citationsList: { display: 'flex', flexDirection: 'column', gap: 4, marginTop: 8 },
  citation: { display: 'flex', gap: 8, alignItems: 'center' },
  citationType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`,
    padding: '1px 6px',
    borderRadius: tokens.radius,
  },
  citationTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  contextSection: { marginTop: 12, paddingTop: 12, borderTop: `1px solid ${tokens.colors.border}` },
  contextItem: { display: 'flex', gap: 8, alignItems: 'center' },
  scoreChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    background: `${tokens.colors.textMuted}20`,
    padding: '1px 5px',
    borderRadius: tokens.radius,
    marginLeft: 'auto',
  },
  historySection: { marginTop: 24 },
  historyLabel: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  historyItem: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  historyQuery: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
};
