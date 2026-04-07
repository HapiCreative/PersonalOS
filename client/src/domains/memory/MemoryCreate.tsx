/**
 * Memory creation form.
 * Section 2.4: memory_nodes (decision, insight, lesson, principle, preference).
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { memoryApi } from '../../api/endpoints';
import type { MemoryType } from '../../types';

const MEMORY_TYPES: MemoryType[] = ['decision', 'insight', 'lesson', 'principle', 'preference'];

interface MemoryCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function MemoryCreate({ onCreated, onCancel }: MemoryCreateProps) {
  const [title, setTitle] = useState('');
  const [memoryType, setMemoryType] = useState<MemoryType>('insight');
  const [content, setContent] = useState('');
  const [context, setContext] = useState('');
  const [reviewAt, setReviewAt] = useState('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await memoryApi.create({
        title: title.trim(),
        memory_type: memoryType,
        content: content || undefined,
        context: context || undefined,
        review_at: reviewAt ? new Date(reviewAt).toISOString() : undefined,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create memory');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Memory</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={styles.input}
          placeholder="Memory title"
          autoFocus
        />
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Type</label>
          <select value={memoryType} onChange={(e) => setMemoryType(e.target.value as MemoryType)} style={styles.select}>
            {MEMORY_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Review Date</label>
          <input type="date" value={reviewAt} onChange={(e) => setReviewAt(e.target.value)} style={styles.input} />
        </div>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Context</label>
        <input value={context} onChange={(e) => setContext(e.target.value)} style={styles.input} placeholder="Situational context..." />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Tags</label>
        <input value={tags} onChange={(e) => setTags(e.target.value)} style={styles.input} placeholder="tag1, tag2, tag3" />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={styles.textArea}
          rows={6}
          placeholder="What did you learn, decide, or realize?"
        />
      </div>

      <div style={styles.actions}>
        <button onClick={handleSubmit} disabled={saving || !title.trim()} style={styles.saveButton}>
          {saving ? 'Creating...' : 'Create Memory'}
        </button>
        <button onClick={onCancel} style={styles.cancelButton}>Cancel</button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 560 },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    marginBottom: 16,
  },
  error: {
    padding: '8px 12px',
    marginBottom: 12,
    background: `${tokens.colors.error}15`,
    borderRadius: tokens.radius,
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
  field: { marginBottom: 12, flex: 1 },
  label: {
    display: 'block',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
    color: tokens.colors.textMuted,
    marginBottom: 4,
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
  select: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    padding: '8px 10px',
  },
  textArea: {
    width: '100%',
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    padding: '8px 10px',
    resize: 'vertical' as const,
    lineHeight: 1.5,
  },
  row: { display: 'flex', gap: 12 },
  actions: { display: 'flex', gap: 8, marginTop: 16 },
  saveButton: {
    padding: '8px 16px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '8px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
  },
};
