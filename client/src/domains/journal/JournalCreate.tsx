/**
 * Journal entry creation form with template support.
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { journalApi, templatesApi } from '../../api/endpoints';
import type { Mood, TemplateResponse } from '../../types';

const MOOD_OPTIONS: { value: Mood; label: string }[] = [
  { value: 'great', label: '✨ Great' },
  { value: 'good', label: '🙂 Good' },
  { value: 'neutral', label: '😐 Neutral' },
  { value: 'low', label: '😔 Low' },
  { value: 'bad', label: '😞 Bad' },
];

interface JournalCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function JournalCreate({ onCreated, onCancel }: JournalCreateProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [mood, setMood] = useState<Mood | undefined>(undefined);
  const [tagsInput, setTagsInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateResponse[]>([]);

  useEffect(() => {
    templatesApi.list({ target_type: 'journal_entry' }).then((res) => {
      setTemplates(res.items);
    }).catch(() => {});
  }, []);

  const applyTemplate = (template: TemplateResponse) => {
    const s = template.structure as Record<string, any>;
    if (s.title) setTitle(s.title);
    if (s.content) setContent(s.content);
    if (s.tags) setTagsInput(s.tags.join(', '));
  };

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean);
      await journalApi.create({
        title: title.trim(),
        content,
        mood,
        tags,
        entry_date: new Date().toISOString().split('T')[0],
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create entry');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Journal Entry</h2>

      {error && <div style={styles.error}>{error}</div>}

      {templates.length > 0 && (
        <div style={styles.templateRow}>
          <span style={styles.label}>Template:</span>
          {templates.map((t) => (
            <button key={t.id} onClick={() => applyTemplate(t)} style={styles.templateButton}>
              {t.name}
            </button>
          ))}
        </div>
      )}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} style={styles.input} placeholder="Entry title" autoFocus />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Mood</label>
        <div style={styles.moodOptions}>
          {MOOD_OPTIONS.map((m) => (
            <button
              key={m.value}
              onClick={() => setMood(mood === m.value ? undefined : m.value)}
              style={{
                ...styles.moodButton,
                background: mood === m.value ? `${tokens.colors.accent}15` : 'transparent',
                borderColor: mood === m.value ? tokens.colors.accent : tokens.colors.border,
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Tags</label>
        <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} style={styles.input} placeholder="tag1, tag2, ..." />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          style={styles.textArea}
          rows={10}
          placeholder="Write your thoughts..."
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
  heading: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 20, color: tokens.colors.text, marginBottom: 16 },
  error: { padding: '8px 12px', marginBottom: 12, background: `${tokens.colors.error}15`, borderRadius: tokens.radius, color: tokens.colors.error, fontFamily: tokens.fonts.sans, fontSize: 13 },
  templateRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' as const },
  templateButton: { padding: '4px 10px', borderRadius: tokens.radius, border: `1px solid ${tokens.colors.violet}`, fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.violet, cursor: 'pointer', background: 'none' },
  field: { marginBottom: 12 },
  label: { display: 'block', fontFamily: tokens.fonts.sans, fontSize: 12, fontWeight: 500, color: tokens.colors.textMuted, marginBottom: 4 },
  input: { width: '100%', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.sans, fontSize: 14, padding: '8px 10px' },
  moodOptions: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  moodButton: { padding: '4px 10px', borderRadius: tokens.radius, border: '1px solid', fontFamily: tokens.fonts.sans, fontSize: 12, cursor: 'pointer', background: 'none', color: tokens.colors.text },
  textArea: { width: '100%', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.sans, fontSize: 14, padding: '12px 14px', resize: 'vertical' as const, lineHeight: 1.7 },
  actions: { display: 'flex', gap: 8, marginTop: 16 },
  saveButton: { padding: '8px 16px', borderRadius: tokens.radius, border: 'none', background: tokens.colors.accent, color: tokens.colors.background, fontFamily: tokens.fonts.sans, fontSize: 13, fontWeight: 600, cursor: 'pointer' },
  cancelButton: { padding: '8px 16px', borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, background: 'none', fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.textMuted, cursor: 'pointer' },
};
