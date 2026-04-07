/**
 * Journal entry detail view with markdown editor, mood selector, tags.
 * Typography: KB / Journal reading uses IBM Plex Sans 400 (Section 9.3).
 */

import { useState, useEffect } from 'react';
import { tokens } from '../../styles/tokens';
import { journalApi } from '../../api/endpoints';
import { EdgeChips } from '../../components/edges/EdgeChips';
import { BacklinksDisplay } from '../../components/edges/BacklinksDisplay';
import type { JournalResponse, Mood } from '../../types';

const MOOD_OPTIONS: { value: Mood; label: string }[] = [
  { value: 'great', label: '✨ Great' },
  { value: 'good', label: '🙂 Good' },
  { value: 'neutral', label: '😐 Neutral' },
  { value: 'low', label: '😔 Low' },
  { value: 'bad', label: '😞 Bad' },
];

interface JournalDetailProps {
  entry: JournalResponse;
  onUpdated: () => void;
}

export function JournalDetail({ entry, onUpdated }: JournalDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(entry.title);
  const [content, setContent] = useState(entry.content);
  const [mood, setMood] = useState<Mood | null>(entry.mood);
  const [tagsInput, setTagsInput] = useState(entry.tags.join(', '));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTitle(entry.title);
    setContent(entry.content);
    setMood(entry.mood);
    setTagsInput(entry.tags.join(', '));
    setEditing(false);
  }, [entry]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean);
      await journalApi.update(entry.node_id, {
        title,
        content,
        mood,
        tags,
      });
      setEditing(false);
      onUpdated();
    } catch {
      // Error handling
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
          <h2 style={styles.title}>{entry.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.date}>{entry.entry_date}</span>
          <span style={styles.wordCount}>{entry.word_count} words</span>
          <span style={styles.nodeId}>{entry.node_id.slice(0, 8)}</span>
        </div>
      </div>

      {/* Mood selector */}
      <div style={styles.moodRow}>
        <span style={styles.label}>Mood:</span>
        {editing ? (
          <div style={styles.moodOptions}>
            {MOOD_OPTIONS.map((m) => (
              <button
                key={m.value}
                onClick={() => setMood(m.value)}
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
        ) : (
          <span style={styles.moodValue}>
            {entry.mood ? MOOD_OPTIONS.find((m) => m.value === entry.mood)?.label : 'Not set'}
          </span>
        )}
      </div>

      {/* Tags */}
      <div style={styles.tagsRow}>
        <span style={styles.label}>Tags:</span>
        {editing ? (
          <input
            value={tagsInput}
            onChange={(e) => setTagsInput(e.target.value)}
            style={styles.tagsInput}
            placeholder="tag1, tag2, ..."
          />
        ) : (
          <div style={styles.tagsDisplay}>
            {entry.tags.length === 0 ? (
              <span style={styles.noTags}>No tags</span>
            ) : (
              entry.tags.map((tag) => (
                <span key={tag} style={styles.tag}>{tag}</span>
              ))
            )}
          </div>
        )}
      </div>

      {/* Content (markdown editor) */}
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
              <button onClick={() => { setEditing(false); setTitle(entry.title); setContent(entry.content); setMood(entry.mood); setTagsInput(entry.tags.join(', ')); }} style={styles.cancelButton}>Cancel</button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            style={styles.textArea}
            rows={12}
            placeholder="Write your journal entry..."
          />
        ) : (
          <div style={styles.content}>
            {content || <span style={styles.noContent}>No content yet</span>}
          </div>
        )}
      </div>

      {/* Edges / Backlinks */}
      <EdgeChips nodeId={entry.node_id} />
      <BacklinksDisplay nodeId={entry.node_id} />
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
  date: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.accent },
  wordCount: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  nodeId: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  moodRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
    padding: '10px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  label: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
    flexShrink: 0,
  },
  moodOptions: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  moodButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: '1px solid',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
    background: 'none',
    color: tokens.colors.text,
  },
  moodValue: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
  },
  tagsRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    marginBottom: 16,
  },
  tagsInput: {
    flex: 1,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    padding: '4px 8px',
  },
  tagsDisplay: { display: 'flex', gap: 6, flexWrap: 'wrap' as const },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    padding: '2px 6px',
    border: `1px solid ${tokens.colors.accent}30`,
    borderRadius: tokens.radius,
  },
  noTags: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
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
    padding: '12px 14px',
    resize: 'vertical' as const,
    lineHeight: 1.7,
  },
  content: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 400,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.7,
    whiteSpace: 'pre-wrap' as const,
  },
  noContent: {
    color: tokens.colors.textMuted,
    fontStyle: 'italic',
  },
};
