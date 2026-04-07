/**
 * KB detail view with markdown editor and compilation pipeline controls.
 * Section 7: KB compilation UI (trigger compile, review draft, accept).
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { kbApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { KBResponse } from '../../types';

const STATUS_COLORS: Record<string, string> = {
  ingest: tokens.colors.textMuted,
  parse: tokens.colors.textMuted,
  compile: tokens.colors.accent,
  review: tokens.colors.warning,
  accept: tokens.colors.success,
  stale: tokens.colors.error,
};

interface KBDetailProps {
  kb: KBResponse;
  onUpdated: () => void;
}

export function KBDetail({ kb, onUpdated }: KBDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(kb.title);
  const [content, setContent] = useState(kb.content);
  const [tags, setTags] = useState(kb.tags.join(', '));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTitle(kb.title);
    setContent(kb.content);
    setTags(kb.tags.join(', '));
    setError(null);
    setEditing(false);
  }, [kb]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await kbApi.update(kb.node_id, {
        title,
        content,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleCompileAction = async (action: string) => {
    setError(null);
    try {
      await kbApi.compile(kb.node_id, action);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Action failed');
    }
  };

  // Determine available compile actions based on current status
  const compileActions: { label: string; action: string; color: string }[] = [];
  if (['ingest', 'stale'].includes(kb.compile_status)) {
    compileActions.push({ label: 'Compile', action: 'compile', color: tokens.colors.accent });
  }
  if (kb.compile_status === 'compile') {
    compileActions.push({ label: 'Compile', action: 'compile', color: tokens.colors.accent });
  }
  if (kb.compile_status === 'review') {
    compileActions.push({ label: 'Accept', action: 'accept', color: tokens.colors.success });
    compileActions.push({ label: 'Reject', action: 'reject', color: tokens.colors.warning });
  }

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
          <h2 style={styles.title}>{kb.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{kb.node_id.slice(0, 8)}</span>
          <span style={styles.date}>Created {new Date(kb.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Compilation status & actions */}
      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Status:</span>
        <span style={{
          ...styles.currentStatus,
          color: STATUS_COLORS[kb.compile_status],
          borderColor: STATUS_COLORS[kb.compile_status],
        }}>
          {kb.compile_status}
        </span>
        <span style={styles.statusLabel}>Stage:</span>
        <span style={styles.statusValue}>{kb.pipeline_stage}</span>
        <span style={styles.statusLabel}>Version:</span>
        <span style={styles.statusValue}>v{kb.compile_version}</span>
        {compileActions.map((ca) => (
          <button
            key={ca.action}
            onClick={() => handleCompileAction(ca.action)}
            style={{ ...styles.actionButton, color: ca.color, borderColor: ca.color }}
          >
            {ca.label}
          </button>
        ))}
      </div>

      {/* Tags */}
      <div style={styles.section}>
        <h3 style={styles.sectionTitle}>Tags</h3>
        {editing ? (
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            style={styles.input}
            placeholder="tag1, tag2, tag3"
          />
        ) : (
          <div style={styles.tagList}>
            {kb.tags.length > 0 ? kb.tags.map((t) => (
              <span key={t} style={styles.tag}>{t}</span>
            )) : (
              <span style={styles.noTags}>No tags</span>
            )}
          </div>
        )}
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
              <button onClick={() => { setEditing(false); setTitle(kb.title); setContent(kb.content); setTags(kb.tags.join(', ')); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={styles.textArea}
            rows={15}
          />
        ) : (
          <div style={styles.content}>{kb.content || 'No content'}</div>
        )}
      </div>

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={kb.node_id} />
      <BacklinksDisplay nodeId={kb.node_id} />
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
  currentStatus: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '3px 8px',
    borderRadius: tokens.radius,
    border: '1px solid',
    textTransform: 'capitalize' as const,
  },
  statusValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.text,
    textTransform: 'capitalize' as const,
  },
  actionButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: '1px solid',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
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
  tagList: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    padding: '2px 8px',
    border: `1px solid ${tokens.colors.accent}40`,
    borderRadius: tokens.radius,
  },
  noTags: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
  },
  input: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '8px 10px',
  },
  content: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 400,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.7,
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
    padding: '4px 10px',
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
    lineHeight: 1.7,
  },
};
