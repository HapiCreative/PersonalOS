/**
 * Inbox item detail view with status management.
 * Supports updating raw_text, title, and status transitions.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { inboxApi } from '../../api/endpoints';
import type { InboxItemResponse, InboxItemStatus } from '../../types';

const STATUS_OPTIONS: InboxItemStatus[] = ['pending', 'promoted', 'dismissed', 'merged', 'archived'];

interface InboxDetailProps {
  item: InboxItemResponse;
  onUpdated: () => void;
}

export function InboxDetail({ item, onUpdated }: InboxDetailProps) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(item.title);
  const [rawText, setRawText] = useState(item.raw_text);
  const [saving, setSaving] = useState(false);

  const handleStatusChange = async (newStatus: InboxItemStatus) => {
    try {
      await inboxApi.update(item.node_id, { status: newStatus });
      onUpdated();
    } catch {
      // Error handling
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await inboxApi.update(item.node_id, { title, raw_text: rawText });
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
          <h2 style={styles.title}>{item.title}</h2>
        )}
        <div style={styles.meta}>
          <span style={styles.nodeId}>{item.node_id.slice(0, 8)}</span>
          <span style={styles.date}>
            Created {new Date(item.created_at).toLocaleString()}
          </span>
        </div>
      </div>

      <div style={styles.statusRow}>
        <span style={styles.statusLabel}>Status:</span>
        <div style={styles.statusButtons}>
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleStatusChange(s)}
              style={{
                ...styles.statusButton,
                background: item.status === s ? tokens.colors.accent : tokens.colors.background,
                color: item.status === s ? tokens.colors.background : tokens.colors.text,
              }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div style={styles.contentSection}>
        <div style={styles.sectionHeader}>
          <h3 style={styles.sectionTitle}>Content</h3>
          {!editing ? (
            <button onClick={() => setEditing(true)} style={styles.editButton}>Edit</button>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleSave} disabled={saving} style={styles.saveButton}>
                {saving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => { setEditing(false); setTitle(item.title); setRawText(item.raw_text); }} style={styles.cancelButton}>
                Cancel
              </button>
            </div>
          )}
        </div>
        {editing ? (
          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            style={styles.textArea}
            rows={8}
          />
        ) : (
          <p style={styles.content}>{item.raw_text}</p>
        )}
      </div>

      {item.promoted_to_node_id && (
        <div style={styles.promotedInfo}>
          Promoted to node: <span style={styles.nodeId}>{item.promoted_to_node_id.slice(0, 8)}</span>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 640,
  },
  header: {
    marginBottom: 20,
  },
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
  meta: {
    display: 'flex',
    gap: 12,
    alignItems: 'center',
  },
  nodeId: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  date: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginBottom: 20,
    padding: '12px 0',
    borderTop: `1px solid ${tokens.colors.border}`,
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  statusLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    fontWeight: 500,
  },
  statusButtons: {
    display: 'flex',
    gap: 6,
    flexWrap: 'wrap' as const,
  },
  statusButton: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  contentSection: {
    marginBottom: 20,
  },
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
    padding: '10px 12px',
    resize: 'vertical' as const,
    lineHeight: 1.5,
  },
  content: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.text,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap' as const,
  },
  promotedInfo: {
    padding: '10px 12px',
    background: `${tokens.colors.success}15`,
    borderRadius: tokens.radius,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.success,
  },
};
