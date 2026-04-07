/**
 * Phase 10: System panel for cache refresh and batch operations.
 * Section 4.1: Signal score materialized view refresh.
 * Section 7: Batch embedding operations.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { adminApi } from '../../api/endpoints';
import type { BatchEmbedResponse, CacheRefreshResponse } from '../../types';

export function SystemPanel() {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<CacheRefreshResponse | null>(null);
  const [embedding, setEmbedding] = useState(false);
  const [embedResult, setEmbedResult] = useState<BatchEmbedResponse | null>(null);
  const [forceRecompute, setForceRecompute] = useState(false);
  const [embedLimit, setEmbedLimit] = useState(200);
  const [error, setError] = useState<string | null>(null);

  const handleCacheRefresh = async () => {
    setRefreshing(true);
    setError(null);
    setRefreshResult(null);
    try {
      const data = await adminApi.refreshCache();
      setRefreshResult(data);
    } catch (e: any) {
      setError(e.message || 'Cache refresh failed');
    } finally {
      setRefreshing(false);
    }
  };

  const handleBatchEmbed = async () => {
    setEmbedding(true);
    setError(null);
    setEmbedResult(null);
    try {
      const data = await adminApi.batchEmbed({
        force_recompute: forceRecompute,
        limit: embedLimit,
      });
      setEmbedResult(data);
    } catch (e: any) {
      setError(e.message || 'Batch embedding failed');
    } finally {
      setEmbedding(false);
    }
  };

  return (
    <div style={styles.panel}>
      {/* Cache Refresh */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Materialized View Refresh</h3>
        <p style={styles.description}>
          Refresh cached signal scores and other materialized views.
          This rebuilds derived data from Core entities for improved query performance.
        </p>
        <button
          onClick={handleCacheRefresh}
          disabled={refreshing}
          style={styles.actionButton}
        >
          {refreshing ? 'Refreshing...' : 'Refresh Materialized Views'}
        </button>

        {refreshResult && (
          <div style={styles.resultBox}>
            <div style={styles.resultTitle}>Refresh Complete</div>
            {Object.entries(refreshResult.materialized_views).map(([name, status]) => (
              <div key={name} style={styles.resultRow}>
                <span style={styles.viewName}>{name}</span>
                <span style={{
                  ...styles.resultValue,
                  color: status === 'refreshed' ? tokens.colors.success : tokens.colors.error,
                }}>
                  {status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={styles.divider} />

      {/* Batch Embedding */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Batch Embedding</h3>
        <p style={styles.description}>
          Generate vector embeddings for nodes that don't have them yet.
          Embeddings enable semantic search and similarity-based retrieval.
        </p>

        <div style={styles.optionRow}>
          <label style={styles.checkbox}>
            <input
              type="checkbox"
              checked={forceRecompute}
              onChange={(e) => setForceRecompute(e.target.checked)}
            />
            <span style={styles.checkboxLabel}>Force recompute existing embeddings</span>
          </label>
        </div>

        <div style={styles.optionRow}>
          <label style={styles.label}>Batch limit:</label>
          <input
            type="number"
            value={embedLimit}
            onChange={(e) => setEmbedLimit(Math.min(1000, Math.max(1, parseInt(e.target.value) || 1)))}
            style={styles.numberInput}
            min={1}
            max={1000}
          />
        </div>

        <button
          onClick={handleBatchEmbed}
          disabled={embedding}
          style={styles.actionButton}
        >
          {embedding ? 'Embedding...' : 'Run Batch Embedding'}
        </button>

        {embedResult && (
          <div style={styles.resultBox}>
            <div style={styles.resultTitle}>Embedding Complete</div>
            <div style={styles.resultRow}>
              <span>Processed:</span>
              <span style={styles.resultValue}>{embedResult.total_processed}</span>
            </div>
            <div style={styles.resultRow}>
              <span>Embedded:</span>
              <span style={{ ...styles.resultValue, color: tokens.colors.success }}>
                {embedResult.total_embedded}
              </span>
            </div>
            <div style={styles.resultRow}>
              <span>Skipped:</span>
              <span style={styles.resultValue}>{embedResult.total_skipped}</span>
            </div>
            {embedResult.total_errors > 0 && (
              <div style={styles.resultRow}>
                <span>Errors:</span>
                <span style={{ ...styles.resultValue, color: tokens.colors.error }}>
                  {embedResult.total_errors}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Global error */}
      {error && <div style={styles.errorMessage}>{error}</div>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {},
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 16,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  description: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    lineHeight: 1.5,
    marginBottom: 16,
  },
  optionRow: {
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  checkbox: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    cursor: 'pointer',
  },
  checkboxLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  label: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    minWidth: 100,
  },
  numberInput: {
    width: 80,
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.text,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '6px 8px',
  },
  actionButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.accent}`,
    background: 'none',
    color: tokens.colors.accent,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
    marginTop: 8,
  },
  divider: {
    borderTop: `1px solid ${tokens.colors.border}`,
    marginBottom: 24,
  },
  resultBox: {
    marginTop: 12,
    padding: 16,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  resultTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.success,
    marginBottom: 12,
  },
  resultRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    padding: '4px 0',
  },
  viewName: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  resultValue: {
    fontFamily: tokens.fonts.mono,
    color: tokens.colors.accent,
  },
  errorMessage: {
    marginTop: 12,
    padding: '8px 12px',
    background: `${tokens.colors.error}15`,
    border: `1px solid ${tokens.colors.error}30`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
};
