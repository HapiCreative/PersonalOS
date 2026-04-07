/**
 * Templates module: create, list, and manage templates.
 * Section 2.4: templates (system configuration).
 */

import { useState, useEffect, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { tokens } from '../../styles/tokens';
import { templatesApi } from '../../api/endpoints';
import type { TemplateResponse, TemplateTargetType } from '../../types';

const TARGET_TYPE_LABELS: Record<TemplateTargetType, string> = {
  goal: 'Goal',
  task: 'Task',
  journal_entry: 'Journal Entry',
};

export function TemplatesModule() {
  const [templates, setTemplates] = useState<TemplateResponse[]>([]);
  const [selected, setSelected] = useState<TemplateResponse | null>(null);
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);

  // Create form state
  const [name, setName] = useState('');
  const [targetType, setTargetType] = useState<TemplateTargetType>('task');
  const [structureJson, setStructureJson] = useState('{}');
  const [error, setError] = useState<string | null>(null);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const res = await templatesApi.list();
      setTemplates(res.items);
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTemplates(); }, [fetchTemplates]);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setError(null);
    try {
      const structure = JSON.parse(structureJson);
      await templatesApi.create({ name: name.trim(), target_type: targetType, structure });
      setCreating(false);
      setName('');
      setStructureJson('{}');
      fetchTemplates();
    } catch (e: any) {
      setError(e.message || 'Failed to create template');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await templatesApi.delete(id);
      setSelected(null);
      fetchTemplates();
    } catch {}
  };

  return (
    <>
      <ListPane title="Templates">
        <div style={styles.toolbar}>
          <button onClick={() => { setCreating(true); setSelected(null); }} style={styles.addButton}>
            + New Template
          </button>
        </div>
        <div style={styles.list}>
          {loading && <div style={styles.empty}>Loading...</div>}
          {!loading && templates.length === 0 && <div style={styles.empty}>No templates</div>}
          {templates.map((t) => (
            <button
              key={t.id}
              onClick={() => { setSelected(t); setCreating(false); }}
              style={{
                ...styles.item,
                background: selected?.id === t.id ? `${tokens.colors.accent}15` : 'transparent',
                borderLeftColor: selected?.id === t.id ? tokens.colors.accent : 'transparent',
              }}
            >
              <span style={styles.itemName}>{t.name}</span>
              <span style={styles.itemType}>{TARGET_TYPE_LABELS[t.target_type]}</span>
            </button>
          ))}
        </div>
      </ListPane>
      <DetailPane>
        {creating ? (
          <div style={styles.form}>
            <h2 style={styles.heading}>New Template</h2>
            {error && <div style={styles.error}>{error}</div>}
            <div style={styles.field}>
              <label style={styles.label}>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} style={styles.input} placeholder="Template name" autoFocus />
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Target Type</label>
              <select value={targetType} onChange={(e) => setTargetType(e.target.value as TemplateTargetType)} style={styles.select}>
                <option value="task">Task</option>
                <option value="journal_entry">Journal Entry</option>
                <option value="goal">Goal</option>
              </select>
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Structure (JSON)</label>
              <textarea value={structureJson} onChange={(e) => setStructureJson(e.target.value)} style={styles.textArea} rows={8} placeholder='{"title": "...", "priority": "high"}' />
            </div>
            <div style={styles.actions}>
              <button onClick={handleCreate} disabled={!name.trim()} style={styles.saveButton}>Create</button>
              <button onClick={() => setCreating(false)} style={styles.cancelButton}>Cancel</button>
            </div>
          </div>
        ) : selected ? (
          <div style={styles.detail}>
            <h2 style={styles.heading}>{selected.name}</h2>
            <div style={styles.meta}>
              <span style={styles.metaItem}>Type: {TARGET_TYPE_LABELS[selected.target_type]}</span>
              <span style={styles.metaItem}>{selected.is_system ? 'System' : 'User'}</span>
            </div>
            <div style={styles.field}>
              <label style={styles.label}>Structure</label>
              <pre style={styles.pre}>{JSON.stringify(selected.structure, null, 2)}</pre>
            </div>
            <button onClick={() => handleDelete(selected.id)} style={styles.deleteButton}>Delete Template</button>
          </div>
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>Select a template or create a new one</p>
          </div>
        )}
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  toolbar: { padding: '8px 12px', borderBottom: `1px solid ${tokens.colors.border}` },
  addButton: { width: '100%', padding: '6px 10px', borderRadius: tokens.radius, border: `1px dashed ${tokens.colors.border}`, fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.accent, cursor: 'pointer', background: 'none' },
  list: { flex: 1, overflowY: 'auto' },
  item: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', padding: '10px 16px', borderLeft: '2px solid transparent', borderBottom: `1px solid ${tokens.colors.border}`, cursor: 'pointer', textAlign: 'left' as const, background: 'none' },
  itemName: { fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.text },
  itemType: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  empty: { padding: 16, color: tokens.colors.textMuted, fontSize: 13, textAlign: 'center' as const },
  form: { maxWidth: 520 },
  detail: { maxWidth: 520 },
  heading: { fontFamily: tokens.fonts.sans, fontWeight: 600, fontSize: 20, color: tokens.colors.text, marginBottom: 16 },
  error: { padding: '8px 12px', marginBottom: 12, background: `${tokens.colors.error}15`, borderRadius: tokens.radius, color: tokens.colors.error, fontFamily: tokens.fonts.sans, fontSize: 13 },
  field: { marginBottom: 12 },
  label: { display: 'block', fontFamily: tokens.fonts.sans, fontSize: 12, fontWeight: 500, color: tokens.colors.textMuted, marginBottom: 4 },
  input: { width: '100%', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.sans, fontSize: 14, padding: '8px 10px' },
  select: { width: '100%', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.mono, fontSize: 13, padding: '8px 10px' },
  textArea: { width: '100%', background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, color: tokens.colors.text, fontFamily: tokens.fonts.mono, fontSize: 13, padding: '8px 10px', resize: 'vertical' as const, lineHeight: 1.5 },
  pre: { background: tokens.colors.surface, border: `1px solid ${tokens.colors.border}`, borderRadius: tokens.radius, padding: '10px 12px', fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.text, whiteSpace: 'pre-wrap' as const, overflow: 'auto' },
  meta: { display: 'flex', gap: 12, marginBottom: 16 },
  metaItem: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  actions: { display: 'flex', gap: 8, marginTop: 16 },
  saveButton: { padding: '8px 16px', borderRadius: tokens.radius, border: 'none', background: tokens.colors.accent, color: tokens.colors.background, fontFamily: tokens.fonts.sans, fontSize: 13, fontWeight: 600, cursor: 'pointer' },
  cancelButton: { padding: '8px 16px', borderRadius: tokens.radius, border: `1px solid ${tokens.colors.border}`, background: 'none', fontFamily: tokens.fonts.sans, fontSize: 13, color: tokens.colors.textMuted, cursor: 'pointer' },
  deleteButton: { padding: '6px 12px', borderRadius: tokens.radius, border: `1px solid ${tokens.colors.error}`, background: 'none', fontFamily: tokens.fonts.sans, fontSize: 12, color: tokens.colors.error, cursor: 'pointer', marginTop: 16 },
  placeholder: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 8 },
  placeholderText: { color: tokens.colors.textMuted, fontFamily: tokens.fonts.sans, fontSize: 14 },
};
