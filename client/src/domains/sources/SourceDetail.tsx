/**
 * Source detail view with triage actions and promotion flow.
 * Section 6: Source triage UI (promote, dismiss, archive).
 * Invariant B-01: Promotion contract (derived_from_source edge auto-created).
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { sourcesApi, llmApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import { EnrichmentDisplay } from '../../components/derived/EnrichmentDisplay';
import { PipelineStatus } from '../../components/derived/PipelineStatus';
import type { SourceResponse, FragmentResponse } from '../../types';

interface SourceDetailProps {
  source: SourceResponse;
  onUpdated: () => void;
}

export function SourceDetail({ source, onUpdated }: SourceDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(source.title);
  const [rawContent, setRawContent] = useState(source.raw_content);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [promoteType, setPromoteType] = useState<string>('kb_entry');
  const [fragments, setFragments] = useState<FragmentResponse[]>([]);

  useEffect(() => {
    setTitle(source.title);
    setRawContent(source.raw_content);
    setError(null);
    setEditing(false);
    setPromoting(false);
    // Load fragments
    sourcesApi.listFragments(source.node_id).then((res) => {
      setFragments(res.items);
    }).catch(() => setFragments([]));
  }, [source]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await sourcesApi.update(source.node_id, { title, raw_content: rawContent });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleTriage = async (action: 'ready' | 'dismissed') => {
    setError(null);
    try {
      await sourcesApi.update(source.node_id, { triage_status: action });
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Triage failed');
    }
  };

  const handlePromote = async () => {
    setError(null);
    try {
      await sourcesApi.promote(source.node_id, { target_type: promoteType });
      setPromoting(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Promotion failed');
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        {editing ? (
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            style={styles.titleInput}
            autoFocus
          />
        ) : (
          <h2 style={styles.title}>{source.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{source.node_id.slice(0, 8)}</span>
          <span style={styles.typeBadge}>{source.source_type}</span>
          <span style={styles.date}>Captured {new Date(source.captured_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Status row */}
      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Processing:</span>
        <span style={styles.statusValue}>{source.processing_status}</span>
        <span style={styles.statusLabel}>Triage:</span>
        <span style={styles.statusValue}>{source.triage_status}</span>
        <span style={styles.statusLabel}>Permanence:</span>
        <span style={styles.statusValue}>{source.permanence}</span>
      </div>

      {/* Triage actions */}
      {source.triage_status === 'unreviewed' && (
        <div style={styles.triageRow}>
          <button onClick={() => handleTriage('ready')} style={styles.triageButton}>
            Mark Ready
          </button>
          <button onClick={() => handleTriage('dismissed')} style={{ ...styles.triageButton, color: tokens.colors.textMuted }}>
            Dismiss
          </button>
          <button onClick={() => setPromoting(!promoting)} style={{ ...styles.triageButton, color: tokens.colors.success }}>
            Promote
          </button>
        </div>
      )}

      {source.triage_status === 'ready' && (
        <div style={styles.triageRow}>
          <button onClick={() => setPromoting(!promoting)} style={{ ...styles.triageButton, color: tokens.colors.success }}>
            Promote
          </button>
          <button onClick={() => handleTriage('dismissed')} style={{ ...styles.triageButton, color: tokens.colors.textMuted }}>
            Dismiss
          </button>
        </div>
      )}

      {/* Promotion flow */}
      {promoting && (
        <div style={styles.promoteSection}>
          <h3 style={styles.sectionTitle}>Promote to:</h3>
          <div style={styles.promoteOptions}>
            {['kb_entry', 'task', 'memory'].map((type) => (
              <button
                key={type}
                onClick={() => setPromoteType(type)}
                style={{
                  ...styles.promoteOption,
                  borderColor: promoteType === type ? tokens.colors.accent : tokens.colors.border,
                  color: promoteType === type ? tokens.colors.accent : tokens.colors.text,
                }}
              >
                {type === 'kb_entry' ? 'KB Entry' : type === 'task' ? 'Task' : 'Memory'}
              </button>
            ))}
          </div>
          <button onClick={handlePromote} style={styles.saveButton}>
            Confirm Promotion
          </button>
        </div>
      )}

      {/* Metadata */}
      {(source.url || source.author || source.platform) && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Metadata</h3>
          <div style={styles.metaGrid}>
            {source.url && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>URL:</span>
                <a href={source.url} target="_blank" rel="noopener noreferrer" style={styles.metaLink}>
                  {source.url}
                </a>
              </div>
            )}
            {source.author && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>Author:</span>
                <span style={styles.metaValue}>{source.author}</span>
              </div>
            )}
            {source.platform && (
              <div style={styles.metaItem}>
                <span style={styles.metaLabel}>Platform:</span>
                <span style={styles.metaValue}>{source.platform}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Phase 9: AI Enrichments from node_enrichments table */}
      <EnrichmentDisplay nodeId={source.node_id} />

      {/* Phase 9: Pipeline status indicators */}
      <PipelineStatus nodeId={source.node_id} />

      {/* Phase 9: Enrich button */}
      <div style={styles.triageRow}>
        <button
          onClick={async () => {
            try {
              await llmApi.enrichSource(source.node_id);
              onUpdated();
            } catch (e: any) {
              setError(e.message || 'Enrichment failed');
            }
          }}
          style={{ ...styles.triageButton, color: tokens.colors.violet }}
        >
          Enrich with AI
        </button>
      </div>

      {/* Content */}
      <div style={styles.section}>
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Content</h3>
          {!editing ? (
            <button onClick={() => setEditing(true)} style={styles.editButton}>Edit</button>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleSave} disabled={saving} style={styles.saveButton}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => { setEditing(false); setTitle(source.title); setRawContent(source.raw_content); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={rawContent}
            onChange={(e) => setRawContent(e.target.value)}
            style={styles.textArea}
            rows={10}
          />
        ) : (
          <p style={styles.content}>{source.raw_content || 'No content'}</p>
        )}
      </div>

      {/* Fragments */}
      {fragments.length > 0 && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Fragments ({fragments.length})</h3>
          <div style={styles.fragmentList}>
            {fragments.map((f) => (
              <div key={f.id} style={styles.fragmentItem}>
                <span style={styles.fragmentType}>{f.fragment_type}</span>
                <span style={styles.fragmentText}>{f.fragment_text.slice(0, 100)}{f.fragment_text.length > 100 ? '...' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={source.node_id} />
      <BacklinksDisplay nodeId={source.node_id} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 640 },
  header: { marginBottom: 16 },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  titleInput: {
    width: '100%',
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '4px 8px',
    marginBottom: 8,
  },
  meta: { display: 'flex', gap: 12, alignItems: 'center' },
  nodeId: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  typeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    padding: '2px 6px',
    border: `1px solid ${tokens.colors.accent}`,
    borderRadius: tokens.radius,
    textTransform: 'uppercase' as const,
  },
  date: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  error: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.error}15`,
    border: `1px solid ${tokens.colors.error}30`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    padding: '12px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
    borderBottom: `1px solid ${tokens.colors.border}`,
    flexWrap: 'wrap' as const,
  },
  statusLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
  },
  statusValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.text,
    textTransform: 'capitalize' as const,
  },
  triageRow: {
    display: 'flex',
    gap: 8,
    marginBottom: 16,
  },
  triageButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
    cursor: 'pointer',
    background: 'none',
    color: tokens.colors.accent,
  },
  promoteSection: {
    padding: 16,
    marginBottom: 16,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  promoteOptions: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  },
  promoteOption: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: '1px solid',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
    background: 'none',
  },
  section: { marginBottom: 20 },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  metaGrid: { display: 'flex', flexDirection: 'column', gap: 4 },
  metaItem: { display: 'flex', gap: 8, alignItems: 'center' },
  metaLabel: { fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.textMuted, minWidth: 60 },
  metaValue: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.text },
  metaLink: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.accent, textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const },
  content: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap' as const,
  },
  editButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  saveButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
  },
  textArea: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '10px 12px',
    resize: 'vertical' as const,
    lineHeight: 1.5,
  },
  fragmentList: { display: 'flex', flexDirection: 'column', gap: 4 },
  fragmentItem: {
    display: 'flex',
    gap: 8,
    padding: '6px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
    alignItems: 'flex-start',
  },
  fragmentType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    textTransform: 'uppercase' as const,
    minWidth: 60,
    flexShrink: 0,
  },
  fragmentText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.text,
    lineHeight: 1.4,
  },
};
