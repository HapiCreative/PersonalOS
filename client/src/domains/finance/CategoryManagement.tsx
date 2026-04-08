/**
 * Finance: Category management view.
 * CRUD with hierarchy display.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeCategoriesApi } from '../../api/endpoints';
import type { FinancialCategoryTreeResponse } from '../../types';

interface CategoryManagementProps {
  onClose: () => void;
}

export function CategoryManagement({ onClose }: CategoryManagementProps) {
  const [categories, setCategories] = useState<FinancialCategoryTreeResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newParentId, setNewParentId] = useState('');
  const [newIcon, setNewIcon] = useState('');
  const [saving, setSaving] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editIcon, setEditIcon] = useState('');

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const tree = await financeCategoriesApi.tree();
      setCategories(tree);
    } catch {
      setCategories([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const handleCreate = useCallback(async () => {
    if (!newName.trim()) {
      setError('Category name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await financeCategoriesApi.create({
        name: newName.trim(),
        parent_id: newParentId || undefined,
        icon: newIcon.trim() || undefined,
      });
      setCreating(false);
      setNewName('');
      setNewParentId('');
      setNewIcon('');
      fetchCategories();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [newName, newParentId, newIcon, fetchCategories]);

  const handleUpdate = useCallback(async (id: string) => {
    if (!editName.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await financeCategoriesApi.update(id, {
        name: editName.trim(),
        icon: editIcon.trim() || undefined,
      });
      setEditingId(null);
      fetchCategories();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [editName, editIcon, fetchCategories]);

  const handleDelete = useCallback(async (id: string) => {
    setError(null);
    try {
      await financeCategoriesApi.delete(id);
      fetchCategories();
    } catch (e: any) {
      // Invariant F-12: deletion blocked if transactions reference it
      setError(e.message);
    }
  }, [fetchCategories]);

  const handleSeed = useCallback(async () => {
    try {
      await financeCategoriesApi.seed();
      fetchCategories();
    } catch (e: any) {
      setError(e.message);
    }
  }, [fetchCategories]);

  const flattenForParentSelect = (trees: FinancialCategoryTreeResponse[], depth = 0): { id: string; name: string; depth: number }[] => {
    const result: { id: string; name: string; depth: number }[] = [];
    for (const cat of trees) {
      result.push({ id: cat.id, name: cat.name, depth });
      if (cat.children?.length) {
        result.push(...flattenForParentSelect(cat.children, depth + 1));
      }
    }
    return result;
  };

  const renderCategory = (cat: FinancialCategoryTreeResponse, depth: number) => {
    const isEditing = editingId === cat.id;
    return (
      <div key={cat.id}>
        <div style={{ ...styles.catRow, paddingLeft: 16 + depth * 20 }}>
          {isEditing ? (
            <div style={styles.editRow}>
              <input
                style={styles.editInput}
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
              />
              <input
                style={{ ...styles.editInput, width: 60 }}
                value={editIcon}
                onChange={(e) => setEditIcon(e.target.value)}
                placeholder="Icon"
              />
              <button style={styles.saveBtn} onClick={() => handleUpdate(cat.id)} disabled={saving}>
                Save
              </button>
              <button style={styles.cancelBtn} onClick={() => setEditingId(null)}>
                Cancel
              </button>
            </div>
          ) : (
            <>
              <span style={styles.catName}>
                {cat.icon && <span style={styles.catIcon}>{cat.icon}</span>}
                {cat.name}
              </span>
              <div style={styles.catActions}>
                {cat.is_system && <span style={styles.systemBadge}>System</span>}
                <button
                  style={styles.actionBtn}
                  onClick={() => {
                    setEditingId(cat.id);
                    setEditName(cat.name);
                    setEditIcon(cat.icon || '');
                  }}
                >
                  Edit
                </button>
                {!cat.is_system && (
                  <button
                    style={{ ...styles.actionBtn, color: tokens.colors.error }}
                    onClick={() => handleDelete(cat.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
            </>
          )}
        </div>
        {cat.children?.map((child) => renderCategory(child, depth + 1))}
      </div>
    );
  };

  const flatCats = flattenForParentSelect(categories);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.heading}>Categories</h2>
        <button style={styles.closeButton} onClick={onClose}>Back</button>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.toolbar}>
        <button style={styles.createBtn} onClick={() => setCreating(!creating)}>
          {creating ? 'Cancel' : '+ New Category'}
        </button>
        {categories.length === 0 && (
          <button style={styles.seedBtn} onClick={handleSeed}>
            Seed Defaults
          </button>
        )}
      </div>

      {creating && (
        <div style={styles.createForm}>
          <input
            style={styles.input}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Category name"
            autoFocus
          />
          <select
            style={styles.input}
            value={newParentId}
            onChange={(e) => setNewParentId(e.target.value)}
          >
            <option value="">No parent (top-level)</option>
            {flatCats.map((c) => (
              <option key={c.id} value={c.id}>
                {'  '.repeat(c.depth)}{c.name}
              </option>
            ))}
          </select>
          <input
            style={styles.input}
            value={newIcon}
            onChange={(e) => setNewIcon(e.target.value)}
            placeholder="Icon (optional)"
          />
          <button style={styles.submitBtn} onClick={handleCreate} disabled={saving}>
            {saving ? 'Creating...' : 'Create'}
          </button>
        </div>
      )}

      <div style={styles.list}>
        {loading && <div style={styles.loadingText}>Loading...</div>}
        {!loading && categories.length === 0 && (
          <div style={styles.loadingText}>No categories. Use "Seed Defaults" to get started.</div>
        )}
        {categories.map((cat) => renderCategory(cat, 0))}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 18,
    color: tokens.colors.text,
    margin: 0,
  },
  closeButton: {
    padding: '4px 12px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  error: {
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    padding: '8px 0',
  },
  toolbar: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  },
  createBtn: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px dashed ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  seedBtn: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
  },
  createForm: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
    padding: 12,
    background: tokens.colors.surface,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    marginBottom: 12,
  },
  input: {
    padding: '6px 8px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.background,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    outline: 'none',
  },
  submitBtn: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: '#000',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    alignSelf: 'flex-start',
  },
  list: { flex: 1, overflowY: 'auto' },
  catRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 16px',
    borderBottom: `1px solid ${tokens.colors.border}`,
    minHeight: 36,
  },
  catName: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  catIcon: { fontSize: 14 },
  catActions: { display: 'flex', alignItems: 'center', gap: 6 },
  systemBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.textMuted,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    padding: '1px 4px',
  },
  actionBtn: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.accent,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '2px 4px',
  },
  editRow: { display: 'flex', alignItems: 'center', gap: 6, flex: 1 },
  editInput: {
    padding: '4px 6px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.background,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    outline: 'none',
    flex: 1,
  },
  saveBtn: {
    padding: '3px 8px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: '#000',
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    cursor: 'pointer',
  },
  cancelBtn: {
    padding: '3px 8px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    cursor: 'pointer',
  },
  loadingText: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
  },
};
