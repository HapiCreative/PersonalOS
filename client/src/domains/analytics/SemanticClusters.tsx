/**
 * Semantic Clusters view (Section 4.9).
 * Shows auto-detected topic clusters from embedding similarity.
 *
 * Invariant D-02: Clusters are recomputable from node embeddings.
 * Invariant D-03: Non-canonical — display convenience only.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { analyticsApi } from '../../api/endpoints';
import type { ClustersListResponse, ClusterResponse } from '../../types';

export function SemanticClusters() {
  const [data, setData] = useState<ClustersListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [computing, setComputing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const fetchClusters = () => {
    setLoading(true);
    setError(null);
    analyticsApi.getClusters()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchClusters();
  }, []);

  const handleRecompute = () => {
    setComputing(true);
    analyticsApi.computeClusters()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setComputing(false));
  };

  if (loading) {
    return <div style={styles.loading}>Loading topic clusters...</div>;
  }

  if (error) {
    return <div style={styles.error}>{error}</div>;
  }

  return (
    <div>
      <div style={styles.toolbar}>
        <span style={styles.count}>
          {data?.total ?? 0} clusters detected
        </span>
        <button
          onClick={handleRecompute}
          disabled={computing}
          style={styles.computeButton}
        >
          {computing ? 'Computing...' : 'Recompute Clusters'}
        </button>
      </div>

      {(!data || data.clusters.length === 0) ? (
        <div style={styles.empty}>
          <p>No semantic clusters detected.</p>
          <p style={{ fontSize: 12, color: tokens.colors.textMuted }}>
            Clusters are computed from node embeddings. Ensure nodes have been embedded,
            then click "Recompute Clusters".
          </p>
        </div>
      ) : (
        <div style={styles.clusterList}>
          {data.clusters.map((cluster) => (
            <ClusterCard
              key={cluster.cluster_id ?? cluster.label}
              cluster={cluster}
              isExpanded={expanded === cluster.cluster_id}
              onToggle={() =>
                setExpanded(
                  expanded === cluster.cluster_id ? null : cluster.cluster_id
                )
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ClusterCard({
  cluster,
  isExpanded,
  onToggle,
}: {
  cluster: ClusterResponse;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div style={styles.card}>
      <button onClick={onToggle} style={styles.cardHeader}>
        <div style={styles.cardTitle}>
          <span style={styles.clusterLabel}>{cluster.label}</span>
          <span style={styles.clusterMeta}>
            {cluster.node_count} nodes · coherence {(cluster.coherence_score * 100).toFixed(0)}%
          </span>
        </div>
        <span style={styles.expandIcon}>{isExpanded ? '\u25B2' : '\u25BC'}</span>
      </button>

      {isExpanded && (
        <div style={styles.memberList}>
          {cluster.members.map((member) => (
            <div key={member.node_id} style={styles.memberRow}>
              <span style={styles.memberType}>{member.type}</span>
              <span style={styles.memberTitle}>{member.title}</span>
              <span style={styles.memberSimilarity}>
                {(member.similarity * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Coherence bar */}
      <div style={styles.coherenceBar}>
        <div
          style={{
            ...styles.coherenceFill,
            width: `${cluster.coherence_score * 100}%`,
            background:
              cluster.coherence_score > 0.85
                ? tokens.colors.success
                : cluster.coherence_score > 0.7
                ? tokens.colors.accent
                : tokens.colors.warning,
          }}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
  },
  count: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
  },
  computeButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  clusterList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 12,
  },
  card: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    overflow: 'hidden' as const,
  },
  cardHeader: {
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
  },
  cardTitle: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 4,
  },
  clusterLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    fontWeight: 600,
    color: tokens.colors.text,
  },
  clusterMeta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  expandIcon: {
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
  memberList: {
    padding: '0 16px 12px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 6,
  },
  memberRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '4px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  memberType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`,
    padding: '2px 6px',
    borderRadius: tokens.radius,
    minWidth: 60,
    textAlign: 'center' as const,
  },
  memberTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    flex: 1,
  },
  memberSimilarity: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  coherenceBar: {
    width: '100%',
    height: 3,
    background: tokens.colors.border,
  },
  coherenceFill: {
    height: '100%',
    transition: 'width 0.3s ease',
  },
  loading: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
  error: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.error,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
  empty: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
    padding: '40px 0',
    textAlign: 'center' as const,
  },
};
