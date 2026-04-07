/**
 * AI Module — Section 5.5: Single AI view with mode selector.
 * Modes: Ask, Plan, Reflect, Improve.
 * Uses violet accent (tokens.colors.violet) for AI/Derived elements.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { llmApi } from '../../api/endpoints';
import type { AIMode, AIModeResponse } from '../../types';

const MODES: { id: AIMode; label: string; placeholder: string }[] = [
  { id: 'ask', label: 'Ask', placeholder: 'Ask a question about your knowledge base...' },
  { id: 'plan', label: 'Plan', placeholder: 'What do you want to plan? E.g., "Break down my Q2 goals into tasks"' },
  { id: 'reflect', label: 'Reflect', placeholder: 'What would you like to reflect on? E.g., "How has my week been?"' },
  { id: 'improve', label: 'Improve', placeholder: 'What would you like to improve? E.g., "How can I unblock my stalled tasks?"' },
];

export function AIModule() {
  const [mode, setMode] = useState<AIMode>('ask');
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AIModeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<AIModeResponse[]>([]);

  const currentMode = MODES.find((m) => m.id === mode)!;

  const handleSubmit = async () => {
    if (!query.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await llmApi.query(mode, query.trim());
      setResult(response);
      setHistory((prev) => [response, ...prev]);
      setQuery('');
    } catch (e: any) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>AI Assistant</h1>
      </div>

      {/* Input area */}
      <div style={styles.inputArea}>
        <div style={styles.inputRow}>
          <select
            value={mode}
            onChange={(e) => { setMode(e.target.value as AIMode); setResult(null); }}
            style={styles.modeSelect}
          >
            {MODES.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          <button
            onClick={handleSubmit}
            disabled={!query.trim() || loading}
            style={{ ...styles.submitButton, opacity: !query.trim() || loading ? 0.5 : 1 }}
          >
            {loading ? 'Thinking...' : 'Send'}
          </button>
        </div>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }
          }}
          placeholder={currentMode.placeholder}
          style={styles.textarea}
          rows={3}
        />
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Result */}
      {result && (
        <div style={styles.resultContainer}>
          <div style={styles.resultHeader}>
            <span style={styles.resultLabel}>{result.mode}</span>
            <span style={styles.meta}>{result.duration_ms}ms | {result.model_version}</span>
          </div>

          {/* Main text */}
          <div style={styles.resultText}>{result.response_text}</div>

          {/* Structured data (mode-specific) */}
          <StructuredOutput mode={result.mode as AIMode} data={result.response_data} />

          {/* Citations (Ask mode) */}
          {result.citations.length > 0 && (
            <div style={styles.section}>
              <span style={styles.sectionLabel}>Citations</span>
              <div style={styles.chipList}>
                {result.citations.map((c, i) => (
                  <span key={i} style={styles.chip}>
                    <span style={styles.chipType}>{c.node_type}</span> {c.title}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Context items */}
          {result.context_items.length > 0 && (
            <div style={styles.section}>
              <span style={styles.sectionLabel}>Context ({result.context_items.length})</span>
              <div style={styles.chipList}>
                {result.context_items.map((item, i) => (
                  <span key={i} style={styles.chip}>
                    <span style={styles.chipType}>{item.node_type}</span>
                    {item.title}
                    <span style={styles.scoreChip}>{(item.combined_score * 100).toFixed(0)}%</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* History */}
      {history.length > 1 && (
        <div style={styles.historySection}>
          <span style={styles.sectionLabel}>Previous</span>
          {history.slice(1, 6).map((h, i) => (
            <div key={i} style={styles.historyItem}>
              <span style={styles.historyMode}>{h.mode}</span>
              <span style={styles.historyQuery}>{h.query}</span>
              <span style={styles.meta}>{h.duration_ms}ms</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Render mode-specific structured data from response_data. */
function StructuredOutput({ mode, data }: { mode: AIMode; data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;

  // Plan mode: milestones + tasks + recommendations
  if (mode === 'plan') {
    const milestones = (data.milestones as Array<Record<string, string>>) || [];
    const tasks = (data.tasks as Array<Record<string, string>>) || [];
    const recs = (data.recommendations as string[]) || [];
    if (!milestones.length && !tasks.length && !recs.length) return null;
    return (
      <div style={{ marginTop: 12 }}>
        {milestones.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Milestones</span>
            {milestones.map((m, i) => (
              <div key={i} style={styles.structuredCard}>
                <strong>{m.title}</strong>
                {m.description && <span style={{ color: tokens.colors.textMuted, fontSize: 12 }}> — {m.description}</span>}
              </div>
            ))}
          </div>
        )}
        {tasks.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Suggested Tasks</span>
            {tasks.map((t, i) => (
              <div key={i} style={styles.structuredCard}>
                {t.title}
                {t.priority && <span style={styles.chipType}> {t.priority}</span>}
              </div>
            ))}
          </div>
        )}
        {recs.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Recommendations</span>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {recs.map((r, i) => <li key={i} style={{ fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text, lineHeight: 1.6 }}>{r}</li>)}
            </ul>
          </div>
        )}
      </div>
    );
  }

  // Reflect mode: patterns + accomplishments + growth areas + insight
  if (mode === 'reflect') {
    const patterns = (data.patterns as string[]) || [];
    const accomplishments = (data.accomplishments as string[]) || [];
    const growthAreas = (data.growth_areas as string[]) || [];
    const insight = data.insight as string || '';
    if (!patterns.length && !accomplishments.length && !insight) return null;
    return (
      <div style={{ marginTop: 12 }}>
        {patterns.length > 0 && <TagSection label="Patterns" items={patterns} color={tokens.colors.violet} />}
        {accomplishments.length > 0 && <TagSection label="Accomplishments" items={accomplishments} color={tokens.colors.success} />}
        {growthAreas.length > 0 && <TagSection label="Growth Areas" items={growthAreas} color={tokens.colors.warning} />}
        {insight && (
          <div style={{ ...styles.insightBox, marginTop: 8 }}>
            <span style={{ ...styles.sectionLabel, color: tokens.colors.violet }}>Key Insight</span>
            <p style={{ fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text, margin: '6px 0 0', lineHeight: 1.5 }}>{insight}</p>
          </div>
        )}
      </div>
    );
  }

  // Improve mode: quick wins + recommendations + items to archive
  if (mode === 'improve') {
    const quickWins = (data.quick_wins as string[]) || [];
    const recs = (data.recommendations as Array<Record<string, string>>) || [];
    const archive = (data.items_to_archive as Array<Record<string, string>>) || [];
    if (!quickWins.length && !recs.length && !archive.length) return null;
    return (
      <div style={{ marginTop: 12 }}>
        {quickWins.length > 0 && <TagSection label="Quick Wins" items={quickWins} color={tokens.colors.success} />}
        {recs.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Recommendations</span>
            {recs.map((r, i) => (
              <div key={i} style={styles.structuredCard}>
                <strong>{r.title}</strong>
                {r.description && <span style={{ display: 'block', color: tokens.colors.textMuted, fontSize: 12, marginTop: 2 }}>{r.description}</span>}
              </div>
            ))}
          </div>
        )}
        {archive.length > 0 && (
          <div style={styles.section}>
            <span style={styles.sectionLabel}>Consider Archiving</span>
            {archive.map((a, i) => (
              <div key={i} style={styles.structuredCard}>
                {a.title} <span style={{ color: tokens.colors.textMuted, fontSize: 12 }}>— {a.reason}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return null;
}

function TagSection({ label, items, color }: { label: string; items: string[]; color: string }) {
  return (
    <div style={styles.section}>
      <span style={styles.sectionLabel}>{label}</span>
      {items.map((item, i) => (
        <div key={i} style={{
          fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
          padding: '5px 10px', background: `${color}08`, borderRadius: tokens.radius,
          borderLeft: `2px solid ${color}`, marginBottom: 3,
        }}>
          {item}
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
    background: tokens.colors.background, overflow: 'auto',
  },
  header: {
    padding: '20px 24px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  title: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 20,
    color: tokens.colors.text, margin: 0,
  },
  inputArea: {
    padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 8,
    maxWidth: 720,
  },
  inputRow: {
    display: 'flex', gap: 8, alignItems: 'center',
  },
  modeSelect: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13,
    background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius, color: tokens.colors.violet,
    padding: '6px 10px', cursor: 'pointer', outline: 'none',
  },
  textarea: {
    fontFamily: tokens.fonts.sans, fontSize: 14,
    background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius, color: tokens.colors.text,
    padding: '10px 12px', resize: 'vertical', outline: 'none',
  },
  submitButton: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 13,
    padding: '6px 16px', background: tokens.colors.violet, color: '#fff',
    border: 'none', borderRadius: tokens.radius, cursor: 'pointer',
    marginLeft: 'auto',
  },
  error: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.error,
    padding: '8px 12px', background: `${tokens.colors.error}15`,
    borderRadius: tokens.radius, margin: '0 24px 12px', maxWidth: 720,
  },
  resultContainer: {
    background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius, padding: 16, margin: '0 24px 16px', maxWidth: 720,
  },
  resultHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12,
  },
  resultLabel: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 14,
    color: tokens.colors.violet, textTransform: 'capitalize',
  },
  meta: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  resultText: {
    fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text,
    lineHeight: 1.6, whiteSpace: 'pre-wrap',
  },
  section: { marginTop: 12, paddingTop: 10, borderTop: `1px solid ${tokens.colors.border}` },
  sectionLabel: {
    fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 11, color: tokens.colors.textMuted,
    textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 6,
  },
  chipList: { display: 'flex', flexDirection: 'column', gap: 3 },
  chip: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    display: 'flex', alignItems: 'center', gap: 6,
  },
  chipType: {
    fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`, padding: '1px 5px', borderRadius: tokens.radius,
  },
  scoreChip: {
    fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.textMuted,
    background: `${tokens.colors.textMuted}20`, padding: '1px 5px', borderRadius: tokens.radius,
    marginLeft: 'auto',
  },
  structuredCard: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text,
    padding: '6px 10px', background: tokens.colors.background,
    borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, marginBottom: 3,
  },
  insightBox: {
    padding: 12, background: `${tokens.colors.violet}10`,
    border: `1px solid ${tokens.colors.violet}30`, borderRadius: tokens.radius,
  },
  historySection: { padding: '0 24px 24px', maxWidth: 720 },
  historyItem: {
    display: 'flex', gap: 8, alignItems: 'center',
    padding: '6px 0', borderBottom: `1px solid ${tokens.colors.border}`,
  },
  historyMode: {
    fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`, padding: '1px 5px', borderRadius: tokens.radius,
    textTransform: 'capitalize',
  },
  historyQuery: {
    fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text, flex: 1,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
};
