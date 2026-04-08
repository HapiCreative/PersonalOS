/**
 * Finance: Transaction detail sheet.
 * All fields, edit capability, audit history link.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import {
  financeTransactionsApi,
  financeCategoriesApi,
} from '../../api/endpoints';
import type {
  FinancialTransactionResponse,
  FinancialTransactionType,
  FinancialTransactionStatus,
  FinancialCategoryTreeResponse,
  TransactionHistoryResponse,
} from '../../types';

const TX_TYPE_LABELS: Record<FinancialTransactionType, string> = {
  income: 'Income',
  expense: 'Expense',
  transfer_in: 'Transfer In',
  transfer_out: 'Transfer Out',
  investment_buy: 'Investment Buy',
  investment_sell: 'Investment Sell',
  dividend: 'Dividend',
  interest: 'Interest',
  fee: 'Fee',
  refund: 'Refund',
  adjustment: 'Adjustment',
};

const STATUS_COLORS: Record<FinancialTransactionStatus, string> = {
  pending: tokens.colors.warning,
  posted: tokens.colors.accent,
  settled: tokens.colors.success,
};

interface TransactionDetailProps {
  transaction: FinancialTransactionResponse;
  onUpdated: () => void;
}

export function TransactionDetail({ transaction, onUpdated }: TransactionDetailProps) {
  const [editing, setEditing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState<TransactionHistoryResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [categories, setCategories] = useState<FinancialCategoryTreeResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Edit fields
  const [editAmount, setEditAmount] = useState(transaction.amount);
  const [editType, setEditType] = useState(transaction.transaction_type);
  const [editStatus, setEditStatus] = useState(transaction.status);
  const [editCategoryId, setEditCategoryId] = useState(transaction.category_id || '');
  const [editCounterparty, setEditCounterparty] = useState(transaction.counterparty || '');
  const [editDescription, setEditDescription] = useState(transaction.description || '');
  const [editTags, setEditTags] = useState((transaction.tags || []).join(', '));

  useEffect(() => {
    setEditAmount(transaction.amount);
    setEditType(transaction.transaction_type);
    setEditStatus(transaction.status);
    setEditCategoryId(transaction.category_id || '');
    setEditCounterparty(transaction.counterparty || '');
    setEditDescription(transaction.description || '');
    setEditTags((transaction.tags || []).join(', '));
    setEditing(false);
    setShowHistory(false);
  }, [transaction]);

  useEffect(() => {
    financeCategoriesApi.tree().then(setCategories).catch(() => {});
  }, []);

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await financeTransactionsApi.getHistory(transaction.id);
      setHistory(res.items);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [transaction.id]);

  useEffect(() => {
    if (showHistory) loadHistory();
  }, [showHistory, loadHistory]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      const amt = parseFloat(editAmount);
      if (isNaN(amt) || amt <= 0) {
        throw new Error('Amount must be a positive number (Invariant F-02)');
      }
      await financeTransactionsApi.update(transaction.id, {
        amount: amt,
        transaction_type: editType,
        status: editStatus,
        category_id: editCategoryId || null,
        counterparty: editCounterparty || null,
        description: editDescription || null,
        tags: editTags ? editTags.split(',').map((t) => t.trim()).filter(Boolean) : null,
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [transaction.id, editAmount, editType, editStatus, editCategoryId, editCounterparty, editDescription, editTags, onUpdated]);

  const handleVoid = useCallback(async () => {
    try {
      await financeTransactionsApi.void(transaction.id);
      onUpdated();
    } catch (e: any) {
      setError(e.message);
    }
  }, [transaction.id, onUpdated]);

  const formatAmount = (amount: string, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(parseFloat(amount));
  };

  const formatDateTime = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  const flattenCategories = (trees: FinancialCategoryTreeResponse[], depth = 0): { id: string; name: string; depth: number }[] => {
    const result: { id: string; name: string; depth: number }[] = [];
    for (const cat of trees) {
      result.push({ id: cat.id, name: cat.name, depth });
      if (cat.children?.length) {
        result.push(...flattenCategories(cat.children, depth + 1));
      }
    }
    return result;
  };

  const flatCats = flattenCategories(categories);
  const isInflow = transaction.signed_amount && parseFloat(transaction.signed_amount) >= 0;

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.headerTop}>
          <span style={{
            ...styles.amount,
            color: isInflow ? tokens.colors.success : tokens.colors.error,
          }}>
            {isInflow ? '+' : '-'}{formatAmount(transaction.amount, transaction.currency)}
          </span>
          <span style={{ ...styles.statusBadge, color: STATUS_COLORS[transaction.status] }}>
            {transaction.status}
          </span>
        </div>
        <span style={styles.typeLabel}>{TX_TYPE_LABELS[transaction.transaction_type]}</span>
        {transaction.is_voided && <span style={styles.voidedBadge}>VOIDED</span>}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {editing ? (
        <div style={styles.form}>
          <label style={styles.label}>Amount</label>
          <input
            style={styles.input}
            value={editAmount}
            onChange={(e) => setEditAmount(e.target.value)}
            type="number"
            step="0.01"
            min="0.01"
          />

          <label style={styles.label}>Type</label>
          <select
            style={styles.input}
            value={editType}
            onChange={(e) => setEditType(e.target.value as FinancialTransactionType)}
          >
            {Object.entries(TX_TYPE_LABELS).map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>

          <label style={styles.label}>Status</label>
          <select
            style={styles.input}
            value={editStatus}
            onChange={(e) => setEditStatus(e.target.value as FinancialTransactionStatus)}
          >
            <option value="pending">Pending</option>
            <option value="posted">Posted</option>
            <option value="settled">Settled</option>
          </select>

          <label style={styles.label}>Category</label>
          <select
            style={styles.input}
            value={editCategoryId}
            onChange={(e) => setEditCategoryId(e.target.value)}
          >
            <option value="">Uncategorized</option>
            {flatCats.map((c) => (
              <option key={c.id} value={c.id}>
                {'  '.repeat(c.depth)}{c.name}
              </option>
            ))}
          </select>

          <label style={styles.label}>Counterparty</label>
          <input
            style={styles.input}
            value={editCounterparty}
            onChange={(e) => setEditCounterparty(e.target.value)}
          />

          <label style={styles.label}>Description</label>
          <textarea
            style={{ ...styles.input, minHeight: 60 }}
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
          />

          <label style={styles.label}>Tags (comma-separated)</label>
          <input
            style={styles.input}
            value={editTags}
            onChange={(e) => setEditTags(e.target.value)}
          />

          <div style={styles.actions}>
            <button style={styles.saveButton} onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
            <button style={styles.cancelButton} onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      ) : (
        <div style={styles.infoGrid}>
          <InfoRow label="Date" value={formatDateTime(transaction.occurred_at)} />
          {transaction.posted_at && (
            <InfoRow label="Posted" value={formatDateTime(transaction.posted_at)} />
          )}
          <InfoRow label="Counterparty" value={transaction.counterparty || '—'} />
          <InfoRow label="Description" value={transaction.description || '—'} />
          <InfoRow
            label="Category"
            value={flatCats.find((c) => c.id === transaction.category_id)?.name || 'Uncategorized'}
          />
          <InfoRow label="Source" value={transaction.source} />
          {transaction.external_id && (
            <InfoRow label="External ID" value={transaction.external_id} />
          )}
          {transaction.transfer_group_id && (
            <InfoRow label="Transfer Group" value={transaction.transfer_group_id} />
          )}
          {transaction.tags && transaction.tags.length > 0 && (
            <div style={styles.tagsRow}>
              {transaction.tags.map((tag) => (
                <span key={tag} style={styles.tag}>{tag}</span>
              ))}
            </div>
          )}

          <div style={styles.meta}>
            <span style={styles.metaText}>Created: {formatDateTime(transaction.created_at)}</span>
            <span style={styles.metaText}>Updated: {formatDateTime(transaction.updated_at)}</span>
          </div>

          <div style={styles.actions}>
            {!transaction.is_voided && (
              <>
                <button style={styles.editButton} onClick={() => setEditing(true)}>Edit</button>
                <button style={styles.voidButton} onClick={handleVoid}>Void</button>
              </>
            )}
            <button
              style={styles.historyButton}
              onClick={() => setShowHistory(!showHistory)}
            >
              {showHistory ? 'Hide History' : 'Audit History'}
            </button>
          </div>
        </div>
      )}

      {showHistory && (
        <div style={styles.historySection}>
          <h3 style={styles.subheading}>Audit Trail</h3>
          {historyLoading && <div style={styles.loadingText}>Loading...</div>}
          {!historyLoading && history.length === 0 && (
            <div style={styles.loadingText}>No history records</div>
          )}
          {history.map((h) => (
            <div key={h.id} style={styles.historyItem}>
              <div style={styles.historyTop}>
                <span style={styles.historyType}>{h.change_type}</span>
                <span style={styles.historyVersion}>v{h.version}</span>
                <span style={styles.historyDate}>{formatDateTime(h.changed_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={infoRowStyles.row}>
      <span style={infoRowStyles.label}>{label}</span>
      <span style={infoRowStyles.value}>{value}</span>
    </div>
  );
}

const infoRowStyles: Record<string, React.CSSProperties> = {
  row: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '6px 0' },
  label: {
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.textMuted,
    flexShrink: 0,
  },
  value: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    textAlign: 'right' as const,
    marginLeft: 12,
    wordBreak: 'break-word' as const,
  },
};

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column' },
  header: { marginBottom: 16 },
  headerTop: { display: 'flex', alignItems: 'center', gap: 12 },
  amount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 24,
    fontWeight: 600,
  },
  statusBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    textTransform: 'uppercase' as const,
  },
  typeLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    marginTop: 4,
    display: 'block',
  },
  voidedBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.error,
    border: `1px solid ${tokens.colors.error}`,
    borderRadius: tokens.radius,
    padding: '2px 6px',
    display: 'inline-block',
    marginTop: 4,
  },
  error: {
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    padding: '8px 0',
  },
  form: { display: 'flex', flexDirection: 'column', gap: 10 },
  label: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  input: {
    padding: '8px 10px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    outline: 'none',
    resize: 'vertical' as const,
  },
  actions: { display: 'flex', gap: 8, marginTop: 12 },
  saveButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: '#000',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  editButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.accent,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  voidButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.error}`,
    background: 'none',
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  historyButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  infoGrid: { display: 'flex', flexDirection: 'column' },
  tagsRow: { display: 'flex', gap: 6, flexWrap: 'wrap' as const, padding: '6px 0' },
  tag: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    borderRadius: tokens.radius,
    padding: '2px 6px',
  },
  meta: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    marginTop: 12,
    paddingTop: 12,
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  metaText: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  historySection: { marginTop: 16, paddingTop: 16, borderTop: `1px solid ${tokens.colors.border}` },
  subheading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    margin: '0 0 8px',
  },
  historyItem: {
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  historyTop: { display: 'flex', alignItems: 'center', gap: 8 },
  historyType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    textTransform: 'uppercase' as const,
  },
  historyVersion: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  historyDate: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  loadingText: {
    padding: 12,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
  },
};
