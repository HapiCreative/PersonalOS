/**
 * Backlinks display in detail pane.
 * Shows incoming edges (nodes that reference this one).
 * Section 9.2: Context layer — backlinks grouped by relation type.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { edgesApi } from '../../api/endpoints';
import type { EdgeResponse, EdgeRelationType } from '../../types';

const RELATION_LABELS: Record<EdgeRelationType, string> = {
  semantic_reference: 'Referenced by',
  derived_from_source: 'Source for',
  parent_child: 'Child of',
  belongs_to: 'Contains',
  goal_tracks_task: 'Tracked by goal',
  goal_tracks_kb: 'Tracked by goal',
  blocked_by: 'Blocks',
  journal_reflects_on: 'Reflected on by',
  source_supports_goal: 'Supported by',
  source_quoted_in: 'Quoted by',
  captured_for: 'Captured by',
};

interface BacklinksDisplayProps {
  nodeId: string;
}

export function BacklinksDisplay({ nodeId }: BacklinksDisplayProps) {
  const [edges, setEdges] = useState<EdgeResponse[]>([]);

  const fetchBacklinks = useCallback(async () => {
    try {
      const res = await edgesApi.getForNode(nodeId, { direction: 'incoming' });
      setEdges(res.items);
    } catch {
      setEdges([]);
    }
  }, [nodeId]);

  useEffect(() => { fetchBacklinks(); }, [fetchBacklinks]);

  if (edges.length === 0) return null;

  // Group by relation type
  const grouped: Record<string, EdgeResponse[]> = {};
  for (const edge of edges) {
    const key = edge.relation_type;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(edge);
  }

  return (
    <div style={styles.section}>
      <h3 style={styles.sectionTitle}>Backlinks</h3>
      {Object.entries(grouped).map(([relType, groupEdges]) => (
        <div key={relType} style={styles.group}>
          <span style={styles.groupLabel}>
            {RELATION_LABELS[relType as EdgeRelationType] || relType}
          </span>
          <div style={styles.chips}>
            {groupEdges.map((edge) => (
              <div key={edge.id} style={styles.chip}>
                <span style={styles.chipId}>{edge.source_id.slice(0, 8)}</span>
                {edge.origin !== 'user' && (
                  <span style={styles.chipOrigin}>{edge.origin}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { marginTop: 20, paddingTop: 16, borderTop: `1px solid ${tokens.colors.border}` },
  sectionTitle: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 14, color: tokens.colors.text, marginBottom: 10 },
  group: { marginBottom: 8 },
  groupLabel: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted, display: 'block', marginBottom: 4 },
  chips: { display: 'flex', flexWrap: 'wrap' as const, gap: 6 },
  chip: { display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius },
  chipId: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.text },
  chipOrigin: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.violet, padding: '1px 4px', background: `${tokens.colors.violet}15`, borderRadius: '2px' },
};
