/**
 * Memory detail view with editing.
 * Section 2.4: memory_nodes (decision, insight, lesson, principle, preference).
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { memoryApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { MemoryResponse } from '../../types';

const TYPE_COLORS: Record<string, string> = {
  decision: tokens.colors.warning,
  insight: tokens.colors.accent,
  lesson: tokens.colors.success,
  principle: tokens.colors.violet,
  preference: tokens.colors.textMuted,
};

interface MemoryDetailProps {
  memory: MemoryResponse;
  onUpdated: () => void;
}

export function MemoryDetail({ memory, onUpdated }: MemoryDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(memory.title);
  const [content, setContent] = useState(memory.content);
  const [context, setContext] = useState(memory.context || '');
  const [reviewAt, setReviewAt] = useState(memory.review_at ? memory.review_at.split('T')[0] : '');
  const [tags, setTags] = useState(memory.tags.join(', '));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setTitle(memory.title);
    setContent(memory.content);
    setContext(memory.context || '');
    setReviewAt(memory.review_at ? memory.review_at.split('T')[0] : '');
    setTags(memory.tags.join(', '));
    setError(null);
    setEditing(false);
  }, [memory]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await memoryApi.update(memory.node_id, {
        title,
        content,
        context: context || undefined,
        review_at: reviewAt ? new Date(reviewAt).toISOString() : null,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message || 'Save failed');
    } finally {
      setSaving(false);
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
          <h2 style={styles.title}>{memory.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{memory.node_id.slice(0, 8)}</span>
          <span style={{
            ...styles.typeBadge,
            color: TYPE_COLORS[memory.memory_type],
            borderColor: TYPE_COLORS[memory.memory_type],
          }}>
            {memory.memory_type}
          </span>
          <span style={styles.date}>Created {new Date(memory.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {/* Review date */}
      {(memory.review_at || editing) && (
        <div style={styles.reviewRow}>
          <span style={styles.fieldLabel}>Review at:</span>
          {editing ? (
            <input
              type="date"
              value={reviewAt}
              onChange={(e) => setReviewAt(e.target.value)}
              style={styles.dateInput}
            />
          ) : (
            <span style={styles.reviewDate}>
              {memory.review_at ? new Date(memory.review_at).toLocaleDateString() : 'Not scheduled'}
            </span>
          )}
        </div>
      )}

      {/* Context */}
      {(memory.context || editing) && (
        <div style={styles.section}>
          <h3 style={styles.sectionTitle}>Context</h3>
          {editing ? (
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              style={styles.textArea}
              rows={3}
              placeholder="Situational context..."
            />
          ) : (
            <p style={styles.contextText}>{memory.context}</p>
          )}
        </div>
      )}

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
            {memory.tags.length > 0 ? memory.tags.map((t) => (
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
              <button onClick={() => { setEditing(false); setTitle(memory.title); setContent(memory.content); setContext(memory.context || ''); setReviewAt(memory.review_at ? memory.review_at.split('T')[0] : ''); setTags(memory.tags.join(', ')); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={styles.textArea}
            rows={8}
          />
        ) : (
          <p style={styles.content}>{memory.content || 'No content'}</p>
        )}
      </div>

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={memory.node_id} />
      <BacklinksDisplay nodeId={memory.node_id} />
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
    padding: '2px 6px',
    border: '1px solid',
    borderRadius: tokens.radius,
    textTransform: 'capitalize' as const,
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
  reviewRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
    padding: '12px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  fieldLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
  },
  reviewDate: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.warning,
  },
  dateInput: {
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
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
  contextText: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontStyle: 'italic',
    lineHeight: 1.5,
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
    lineHeight: 1.5,
  },
};
