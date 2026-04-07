/**
 * KB entry creation form.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { kbApi } from '../../api/endpoints';

interface KBCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function KBCreate({ onCreated, onCancel }: KBCreateProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await kbApi.create({
        title: title.trim(),
        content: content || undefined,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create KB entry');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New KB Entry</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={styles.input}
          placeholder="Knowledge entry title"
          autoFocus
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Tags</label>
        <input
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          style={styles.input}
          placeholder="tag1, tag2, tag3"
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={styles.textArea}
          rows={10}
          placeholder="Write your knowledge entry..."
        />
      </div>

      <div style={styles.actions}>
        <button onClick={handleSubmit} disabled={saving || !title.trim()} style={styles.saveButton}>
          {saving ? 'Creating...' : 'Create Entry'}
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
  field: { marginBottom: 12 },
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
    lineHeight: 1.7,
  },
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
