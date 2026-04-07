/**
 * Source capture form.
 * Section 6: Source capture workflow (Stage 1 - capture).
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { sourcesApi } from '../../api/endpoints';
import type { SourceType, Permanence } from '../../types';

const SOURCE_TYPES: SourceType[] = ['article', 'tweet', 'bookmark', 'note', 'podcast', 'video', 'pdf', 'other'];
const PERMANENCE_OPTIONS: Permanence[] = ['ephemeral', 'reference', 'canonical'];

interface SourceCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function SourceCreate({ onCreated, onCancel }: SourceCreateProps) {
  const [title, setTitle] = useState('');
  const [rawContent, setRawContent] = useState('');
  const [sourceType, setSourceType] = useState<SourceType>('article');
  const [url, setUrl] = useState('');
  const [author, setAuthor] = useState('');
  const [platform, setPlatform] = useState('');
  const [captureContext, setCaptureContext] = useState('');
  const [permanence, setPermanence] = useState<Permanence>('reference');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await sourcesApi.create({
        title: title.trim(),
        source_type: sourceType,
        url: url || undefined,
        author: author || undefined,
        platform: platform || undefined,
        capture_context: captureContext || undefined,
        raw_content: rawContent || undefined,
        permanence,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to capture source');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Capture Source</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={styles.input}
          placeholder="Source title"
          autoFocus
        />
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Type</label>
          <select value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)} style={styles.select}>
            {SOURCE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Permanence</label>
          <select value={permanence} onChange={(e) => setPermanence(e.target.value as Permanence)} style={styles.select}>
            {PERMANENCE_OPTIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>URL</label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} style={styles.input} placeholder="https://..." />
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Author</label>
          <input value={author} onChange={(e) => setAuthor(e.target.value)} style={styles.input} placeholder="Author name" />
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Platform</label>
          <input value={platform} onChange={(e) => setPlatform(e.target.value)} style={styles.input} placeholder="e.g. Twitter, Medium" />
        </div>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Capture Context</label>
        <input value={captureContext} onChange={(e) => setCaptureContext(e.target.value)} style={styles.input} placeholder="Why are you capturing this?" />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Content</label>
        <textarea
          value={rawContent}
          onChange={(e) => setRawContent(e.target.value)}
          style={styles.textArea}
          rows={6}
          placeholder="Paste source content here..."
        />
      </div>

      <div style={styles.actions}>
        <button onClick={handleSubmit} disabled={saving || !title.trim()} style={styles.saveButton}>
          {saving ? 'Capturing...' : 'Capture Source'}
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
