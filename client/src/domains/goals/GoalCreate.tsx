/**
 * Goal creation form with timeframe fields.
 * Section 2.4: goal_nodes companion table.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { goalsApi } from '../../api/endpoints';

interface GoalCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function GoalCreate({ onCreated, onCancel }: GoalCreateProps) {
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [timeframeLabel, setTimeframeLabel] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!title.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await goalsApi.create({
        title: title.trim(),
        summary: summary || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        timeframe_label: timeframeLabel || undefined,
        notes: notes || undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create goal');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Goal</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.field}>
        <label style={styles.label}>Title</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          style={styles.input}
          placeholder="Goal title"
          autoFocus
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Summary</label>
        <input
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          style={styles.input}
          placeholder="Brief description"
        />
      </div>

      <div style={styles.row}>
        <div style={styles.field}>
          <label style={styles.label}>Start Date</label>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={styles.input}
          />
        </div>
        <div style={styles.field}>
          <label style={styles.label}>End Date</label>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={styles.input}
          />
        </div>
        <div style={styles.field}>
          <label style={styles.label}>Timeframe</label>
          <input
            value={timeframeLabel}
            onChange={(e) => setTimeframeLabel(e.target.value)}
            style={styles.input}
            placeholder="e.g. Q1 2026"
          />
        </div>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Notes</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          style={styles.textArea}
          rows={4}
          placeholder="Optional notes..."
        />
      </div>

      <div style={styles.actions}>
        <button onClick={handleSubmit} disabled={saving || !title.trim()} style={styles.saveButton}>
          {saving ? 'Creating...' : 'Create Goal'}
        </button>
        <button onClick={onCancel} style={styles.cancelButton}>Cancel</button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 560, padding: '0' },
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
