/**
 * Enrichment display component (Section 4.8).
 * Shows AI-generated enrichments on source items.
 * Invariant S-05: Displays only active enrichments.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { enrichmentsApi } from '../../api/endpoints';
import type { EnrichmentResponse } from '../../types';

interface EnrichmentDisplayProps {
  nodeId: string;
}

export function EnrichmentDisplay({ nodeId }: EnrichmentDisplayProps) {
  const [enrichments, setEnrichments] = useState<EnrichmentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoading(true);
    enrichmentsApi.getForNode(nodeId)
      .then((res) => setEnrichments(res.items))
      .catch(() => setEnrichments([]))
      .finally(() => setLoading(false));
  }, [nodeId]);

  if (loading) {
    return <div style={styles.loading}>Loading enrichments...</div>;
  }

  if (enrichments.length === 0) {
    return null;
  }

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <span style={styles.headerLabel}>AI Enrichments</span>
        <span style={styles.count}>{enrichments.length}</span>
      </div>
      {enrichments.map((e) => (
        <div key={e.id} style={styles.enrichmentCard}>
          <div
            style={styles.enrichmentHeader}
            onClick={() => toggleExpand(e.id)}
          >
            <span style={styles.typeChip}>{e.enrichment_type}</span>
            <span style={styles.statusChip(e.status)}>{e.status}</span>
            {e.model_version && (
              <span style={styles.versionChip}>{e.model_version}</span>
            )}
          </div>
          {(expanded[e.id] || e.enrichment_type === 'summary') && (
            <div style={styles.payload}>
              {e.enrichment_type === 'summary' && e.payload.text && (
                <p style={styles.summaryText}>{e.payload.text as string}</p>
              )}
              {e.enrichment_type === 'takeaways' && Array.isArray(e.payload.items) && (
                <ul style={styles.takeawaysList}>
                  {(e.payload.items as string[]).map((item, i) => (
                    <li key={i} style={styles.takeawayItem}>{item}</li>
                  ))}
                </ul>
              )}
              {e.enrichment_type === 'entities' && Array.isArray(e.payload.items) && (
                <div style={styles.entitiesGrid}>
                  {(e.payload.items as Array<Record<string, string>>).map((ent, i) => (
                    <span key={i} style={styles.entityChip}>
                      {ent.name}
                      {ent.type && <span style={styles.entityType}>{ent.type}</span>}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties | ((...args: any[]) => React.CSSProperties)> = {
  container: {
    marginTop: 16,
    padding: 12,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  loading: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    padding: 8,
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  headerLabel: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.violet,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  count: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  enrichmentCard: {
    marginBottom: 6,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    overflow: 'hidden',
  },
  enrichmentHeader: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    padding: '6px 10px',
    cursor: 'pointer',
    background: tokens.colors.background,
  },
  typeChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.violet,
    background: `${tokens.colors.violet}15`,
    padding: '1px 6px',
    borderRadius: tokens.radius,
  },
  statusChip: (status: string): React.CSSProperties => ({
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: status === 'completed' ? tokens.colors.success : tokens.colors.textMuted,
    padding: '1px 5px',
    borderRadius: tokens.radius,
    background: status === 'completed' ? `${tokens.colors.success}15` : `${tokens.colors.textMuted}15`,
  }),
  versionChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    marginLeft: 'auto',
  },
  payload: {
    padding: '8px 10px',
  },
  summaryText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    lineHeight: 1.5,
    margin: 0,
  },
  takeawaysList: {
    margin: 0,
    paddingLeft: 16,
  },
  takeawayItem: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    lineHeight: 1.5,
  },
  entitiesGrid: {
    display: 'flex',
    flexWrap: 'wrap' as const,
    gap: 4,
  },
  entityChip: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    background: `${tokens.colors.violet}10`,
    padding: '2px 8px',
    borderRadius: tokens.radius,
    display: 'inline-flex',
    gap: 4,
    alignItems: 'center',
  },
  entityType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
  },
};
