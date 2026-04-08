/**
 * Edge chips display + manual edge creation.
 * Shows outgoing edges as link chips with type-pair validation.
 * Section 2.3: Edge creation with G-01, G-02 validation.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { edgesApi, searchApi, edgeStateApi } from '../../api/endpoints';
import type { EdgeResponse, EdgeRelationType, NodeResponse } from '../../types';

const RELATION_LABELS: Record<EdgeRelationType, string> = {
  semantic_reference: 'References',
  derived_from_source: 'Derived from',
  parent_child: 'Parent/Child',
  belongs_to: 'Belongs to',
  goal_tracks_task: 'Tracks task',
  goal_tracks_kb: 'Tracks KB',
  blocked_by: 'Blocked by',
  journal_reflects_on: 'Reflects on',
  source_supports_goal: 'Supports goal',
  source_quoted_in: 'Quoted in',
  captured_for: 'Captured for',
};

const RELATION_TYPES: EdgeRelationType[] = [
  'semantic_reference', 'parent_child', 'belongs_to', 'goal_tracks_task',
  'goal_tracks_kb', 'blocked_by', 'journal_reflects_on', 'derived_from_source',
  'source_supports_goal', 'source_quoted_in', 'captured_for',
];

interface EdgeChipsProps {
  nodeId: string;
}

export function EdgeChips({ nodeId }: EdgeChipsProps) {
  const [edges, setEdges] = useState<EdgeResponse[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<NodeResponse[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<NodeResponse | null>(null);
  const [relationType, setRelationType] = useState<EdgeRelationType>('semantic_reference');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // Phase PB: Edge weight editing
  const [editingWeight, setEditingWeight] = useState<string | null>(null);
  const [weightValue, setWeightValue] = useState('');

  const fetchEdges = useCallback(async () => {
    try {
      const res = await edgesApi.getForNode(nodeId, { direction: 'outgoing' });
      setEdges(res.items);
    } catch {
      setEdges([]);
    }
  }, [nodeId]);

  useEffect(() => { fetchEdges(); }, [fetchEdges]);

  // Search for link targets
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timeout = setTimeout(async () => {
      try {
        const res = await searchApi.search(searchQuery, { limit: 5 });
        // Filter out self
        setSearchResults(res.items.filter((n) => n.id !== nodeId));
      } catch {
        setSearchResults([]);
      }
    }, 200);
    return () => clearTimeout(timeout);
  }, [searchQuery, nodeId]);

  const handleCreateEdge = async () => {
    if (!selectedTarget) return;
    setError(null);
    setLoading(true);
    try {
      await edgesApi.create({
        source_id: nodeId,
        target_id: selectedTarget.id,
        relation_type: relationType,
      });
      setShowCreate(false);
      setSelectedTarget(null);
      setSearchQuery('');
      fetchEdges();
    } catch (e: any) {
      setError(e.message || 'Failed to create edge');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteEdge = async (edgeId: string) => {
    try {
      await edgesApi.delete(edgeId);
      fetchEdges();
    } catch {}
  };

  // Phase PB: Edge weight user override
  const handleWeightUpdate = async (edgeId: string) => {
    const w = parseFloat(weightValue);
    if (isNaN(w) || w < 0 || w > 1) {
      setError('Weight must be between 0.0 and 1.0');
      return;
    }
    try {
      await edgeStateApi.updateWeight(edgeId, w);
      setEditingWeight(null);
      setWeightValue('');
      fetchEdges();
    } catch (e: any) {
      setError(e.message || 'Failed to update weight');
    }
  };

  return (
    <div style={styles.section}>
      <div style={styles.sectionHeader}>
        <h3 style={styles.sectionTitle}>Links</h3>
        <button onClick={() => setShowCreate(!showCreate)} style={styles.addButton}>
          {showCreate ? 'Cancel' : '+ Link'}
        </button>
      </div>

      {showCreate && (
        <div style={styles.createForm}>
          {error && <div style={styles.error}>{error}</div>}
          <div style={styles.createRow}>
            <select
              value={relationType}
              onChange={(e) => setRelationType(e.target.value as EdgeRelationType)}
              style={styles.select}
            >
              {RELATION_TYPES.map((r) => (
                <option key={r} value={r}>{RELATION_LABELS[r]}</option>
              ))}
            </select>
          </div>
          <input
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setSelectedTarget(null); }}
            style={styles.searchInput}
            placeholder="Search for target node..."
          />
          {searchResults.length > 0 && !selectedTarget && (
            <div style={styles.searchResults}>
              {searchResults.map((node) => (
                <button
                  key={node.id}
                  onClick={() => { setSelectedTarget(node); setSearchQuery(node.title); }}
                  style={styles.searchResult}
                >
                  <span style={styles.resultType}>{node.type}</span>
                  <span>{node.title}</span>
                </button>
              ))}
            </div>
          )}
          {selectedTarget && (
            <button onClick={handleCreateEdge} disabled={loading} style={styles.createButton}>
              {loading ? 'Creating...' : `Link to "${selectedTarget.title}"`}
            </button>
          )}
        </div>
      )}

      {edges.length === 0 && !showCreate && (
        <p style={styles.noEdges}>No outgoing links</p>
      )}

      <div style={styles.chips}>
        {edges.map((edge) => (
          <div key={edge.id} style={styles.chip}>
            <span style={styles.chipRelation}>{RELATION_LABELS[edge.relation_type]}</span>
            <span style={styles.chipTarget}>{edge.target_id.slice(0, 8)}</span>
            {edge.origin !== 'user' && (
              <span style={styles.chipOrigin}>{edge.origin}</span>
            )}
            {/* Phase PB: Weight display + edit */}
            {editingWeight === edge.id ? (
              <span style={styles.weightEdit}>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.1"
                  value={weightValue}
                  onChange={(e) => setWeightValue(e.target.value)}
                  style={styles.weightInput}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleWeightUpdate(edge.id);
                    if (e.key === 'Escape') { setEditingWeight(null); setWeightValue(''); }
                  }}
                />
                <button onClick={() => handleWeightUpdate(edge.id)} style={styles.weightSave}>✓</button>
              </span>
            ) : (
              <button
                onClick={() => { setEditingWeight(edge.id); setWeightValue(String(edge.weight)); }}
                style={styles.chipWeight}
                title="Click to edit weight (Phase PB)"
              >
                w:{edge.weight.toFixed(1)}
              </button>
            )}
            <button onClick={() => handleDeleteEdge(edge.id)} style={styles.chipRemove}>×</button>
          </div>
        ))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { marginBottom: 20 },
  sectionHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  sectionTitle: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 14, color: tokens.colors.text },
  addButton: { padding: '4px 10px', borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.accent, cursor: 'pointer', background: 'none' },
  createForm: { marginBottom: 12, padding: '10px', background: tokens.colors.surface, borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}` },
  createRow: { marginBottom: 8 },
  select: { width: '100%', background: tokens.colors.background, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.mono, fontSize: 12, padding: '6px 8px' },
  searchInput: { width: '100%', background: tokens.colors.background, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.sans, fontSize: 13, padding: '6px 8px', marginBottom: 4 },
  searchResults: { maxHeight: 150, overflowY: 'auto', border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, marginBottom: 8 },
  searchResult: { display: 'flex', gap: 8, width: '100%', padding: '6px 8px', border: 'none', cursor: 'pointer', textAlign: 'left' as const, color: tokens.colors.text, fontFamily: tokens.fonts.sans, fontSize: 13, background: 'none' },
  resultType: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted, minWidth: 60 },
  createButton: { padding: '6px 12px', borderRadius: tokens.radius, border: 'none', background: tokens.colors.accent, color: tokens.colors.background, fontFamily: tokens.fonts.sans, fontSize: 12, fontWeight: 600, cursor: 'pointer' },
  error: { padding: '6px 8px', marginBottom: 8, background: `${tokens.colors.error}15`, borderRadius: tokens.radius, color: tokens.colors.error, fontFamily: tokens.fonts.sans, fontSize: 12 },
  noEdges: { fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.textMuted },
  chips: { display: 'flex', flexWrap: 'wrap' as const, gap: 6 },
  chip: { display: 'flex', alignItems: 'center', gap: 6, padding: '3px 8px', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius },
  chipRelation: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.accent },
  chipTarget: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.text },
  chipOrigin: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.violet, padding: '1px 4px', background: `${tokens.colors.violet}15`, borderRadius: '2px' },
  chipWeight: { border: 'none', background: `${tokens.colors.accent}10`, color: tokens.colors.accent, cursor: 'pointer', fontFamily: tokens.fonts.mono, fontSize: 10, padding: '1px 4px', borderRadius: '2px' },
  weightEdit: { display: 'flex', alignItems: 'center', gap: 2 },
  weightInput: { width: 40, fontFamily: tokens.fonts.mono, fontSize: 10, padding: '1px 3px', border: `1px solid ${tokens.colors.accent}`, borderRadius: '2px', background: tokens.colors.background, color: tokens.colors.text },
  weightSave: { border: 'none', background: 'none', color: tokens.colors.success, cursor: 'pointer', fontSize: 12, padding: '0 2px' },
  chipRemove: { border: 'none', background: 'none', color: tokens.colors.textMuted, cursor: 'pointer', fontSize: 14, padding: '0 2px', lineHeight: 1 },
};
