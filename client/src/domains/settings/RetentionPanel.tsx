/**
 * Phase 10: Retention policy UI.
 * Section 1.7: Deletion & Retention Policy enforcement.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { adminApi } from '../../api/endpoints';
import type { RetentionStatsResponse, RetentionEnforceResponse } from '../../types';

export function RetentionPanel() {
  const [stats, setStats] = useState<RetentionStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [enforcing, setEnforcing] = useState(false);
  const [result, setResult] = useState<RetentionEnforceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await adminApi.retentionStats();
      setStats(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load retention stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleEnforce = async () => {
    setEnforcing(true);
    setError(null);
    setResult(null);
    try {
      const data = await adminApi.enforceRetention();
      setResult(data);
      // Refresh stats after enforcement
      await fetchStats();
    } catch (e: any) {
      setError(e.message || 'Retention enforcement failed');
    } finally {
      setEnforcing(false);
    }
  };

  return (
    <div style={styles.panel}>
      <h3 style={styles.sectionTitle}>Retention Policy</h3>
      <p style={styles.description}>
        Manage data retention for operational data. User-owned data is never auto-deleted.
        Only recomputable and operational data is subject to retention policies.
      </p>

      {loading && <div style={styles.loading}>Loading retention stats...</div>}

      {stats && (
        <div style={styles.statsGrid}>
          {/* Pipeline Jobs */}
          <div style={styles.statCard}>
            <h4 style={styles.statTitle}>Pipeline Jobs</h4>
            <div style={styles.statRow}>
              <span>Total jobs:</span>
              <span style={styles.statValue}>{stats.pipeline_jobs.total}</span>
            </div>
            <div style={styles.statRow}>
              <span>Eligible for cleanup:</span>
              <span style={{
                ...styles.statValue,
                color: stats.pipeline_jobs.eligible_for_cleanup > 0
                  ? tokens.colors.warning
                  : tokens.colors.success,
              }}>
                {stats.pipeline_jobs.eligible_for_cleanup}
              </span>
            </div>
            <div style={styles.statRow}>
              <span>Retention period:</span>
              <span style={styles.statValue}>{stats.pipeline_jobs.retention_days} days</span>
            </div>
          </div>

          {/* Enrichments */}
          <div style={styles.statCard}>
            <h4 style={styles.statTitle}>Superseded Enrichments</h4>
            <div style={styles.statRow}>
              <span>Total enrichments:</span>
              <span style={styles.statValue}>{stats.enrichments.total}</span>
            </div>
            <div style={styles.statRow}>
              <span>Eligible for cleanup:</span>
              <span style={{
                ...styles.statValue,
                color: stats.enrichments.superseded_eligible_for_cleanup > 0
                  ? tokens.colors.warning
                  : tokens.colors.success,
              }}>
                {stats.enrichments.superseded_eligible_for_cleanup}
              </span>
            </div>
            <div style={styles.statRow}>
              <span>Retention period:</span>
              <span style={styles.statValue}>{stats.enrichments.retention_days} days</span>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={handleEnforce}
        disabled={enforcing}
        style={styles.enforceButton}
      >
        {enforcing ? 'Running cleanup...' : 'Run Retention Cleanup'}
      </button>

      {result && (
        <div style={styles.resultBox}>
          <div style={styles.resultTitle}>Cleanup Complete</div>
          <div style={styles.resultRow}>
            <span>Pipeline jobs deleted:</span>
            <span style={styles.resultValue}>{result.pipeline_jobs_deleted}</span>
          </div>
          <div style={styles.resultRow}>
            <span>Enrichments deleted:</span>
            <span style={styles.resultValue}>{result.enrichments_deleted}</span>
          </div>
          {result.errors.length > 0 && (
            <div style={styles.errorList}>
              {result.errors.map((err, i) => (
                <div key={i} style={styles.errorItem}>{err}</div>
              ))}
            </div>
          )}
        </div>
      )}

      {error && <div style={styles.errorMessage}>{error}</div>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {},
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
    marginBottom: 20,
  },
  loading: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    padding: 16,
  },
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    marginBottom: 20,
  },
  statCard: {
    padding: 16,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  statTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.text,
    marginBottom: 12,
  },
  statRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    padding: '3px 0',
  },
  statValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.accent,
  },
  enforceButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.warning}`,
    background: 'none',
    color: tokens.colors.warning,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
  resultBox: {
    marginTop: 16,
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
  resultValue: {
    fontFamily: tokens.fonts.mono,
    color: tokens.colors.accent,
  },
  errorList: {
    marginTop: 8,
    borderTop: `1px solid ${tokens.colors.border}`,
    paddingTop: 8,
  },
  errorItem: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.error,
    padding: '2px 0',
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
