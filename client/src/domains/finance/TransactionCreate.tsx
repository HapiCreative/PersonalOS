/**
 * Finance: Manual transaction entry form.
 * Account, amount, type, category (hierarchical dropdown), date.
 * Smart defaults (last account, today).
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import {
  financeTransactionsApi,
  financeAccountsApi,
  financeCategoriesApi,
} from '../../api/endpoints';
import type {
  AccountResponse,
  FinancialTransactionType,
  FinancialCategoryTreeResponse,
} from '../../types';

const TX_TYPES: { value: FinancialTransactionType; label: string }[] = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
  { value: 'transfer_out', label: 'Transfer Out' },
  { value: 'transfer_in', label: 'Transfer In' },
  { value: 'investment_buy', label: 'Investment Buy' },
  { value: 'investment_sell', label: 'Investment Sell' },
  { value: 'dividend', label: 'Dividend' },
  { value: 'interest', label: 'Interest' },
  { value: 'fee', label: 'Fee' },
  { value: 'refund', label: 'Refund' },
  { value: 'adjustment', label: 'Adjustment' },
];

interface TransactionCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function TransactionCreate({ onCreated, onCancel }: TransactionCreateProps) {
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [categories, setCategories] = useState<FinancialCategoryTreeResponse[]>([]);
  const [loading, setLoading] = useState(true);

  // Form fields with smart defaults
  const [accountId, setAccountId] = useState('');
  const [amount, setAmount] = useState('');
  const [transactionType, setTransactionType] = useState<FinancialTransactionType>('expense');
  const [categoryId, setCategoryId] = useState('');
  const [counterparty, setCounterparty] = useState('');
  const [description, setDescription] = useState('');
  const [occurredAt, setOccurredAt] = useState('');
  const [tags, setTags] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load reference data and smart defaults
  useEffect(() => {
    Promise.all([
      financeAccountsApi.list({ is_active: true, limit: 100 }),
      financeCategoriesApi.tree(),
      financeTransactionsApi.getDefaults(),
    ]).then(([accs, cats, defaults]) => {
      setAccounts(accs.items);
      setCategories(cats);
      // Smart defaults: last used account, today's date
      if (defaults.last_used_account_id) {
        setAccountId(defaults.last_used_account_id);
      } else if (accs.items.length > 0) {
        setAccountId(accs.items[0].node_id);
      }
      setOccurredAt(defaults.default_date);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

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

  const handleSubmit = useCallback(async () => {
    if (!accountId) {
      setError('Please select an account');
      return;
    }
    const amt = parseFloat(amount);
    // Invariant F-02: amount must be positive
    if (isNaN(amt) || amt <= 0) {
      setError('Amount must be a positive number (Invariant F-02)');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const account = accounts.find((a) => a.node_id === accountId);
      await financeTransactionsApi.create({
        account_id: accountId,
        transaction_type: transactionType,
        amount: amt,
        currency: account?.currency || 'USD',
        category_id: categoryId || undefined,
        counterparty: counterparty.trim() || undefined,
        description: description.trim() || undefined,
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : undefined,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [accountId, amount, transactionType, categoryId, counterparty, description, occurredAt, tags, accounts, onCreated]);

  if (loading) {
    return <div style={styles.loading}>Loading...</div>;
  }

  const flatCats = flattenCategories(categories);

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Transaction</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.form}>
        <label style={styles.label}>Account *</label>
        <select
          style={styles.input}
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
        >
          <option value="">Select account...</option>
          {accounts.map((a) => (
            <option key={a.node_id} value={a.node_id}>{a.title}</option>
          ))}
        </select>

        <label style={styles.label}>Amount *</label>
        <input
          style={styles.input}
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          type="number"
          step="0.01"
          min="0.01"
          placeholder="0.00"
          autoFocus
        />

        <label style={styles.label}>Type</label>
        <select
          style={styles.input}
          value={transactionType}
          onChange={(e) => setTransactionType(e.target.value as FinancialTransactionType)}
        >
          {TX_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <label style={styles.label}>Category</label>
        <select
          style={styles.input}
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
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
          value={counterparty}
          onChange={(e) => setCounterparty(e.target.value)}
          placeholder="Merchant, employer, etc."
        />

        <label style={styles.label}>Date</label>
        <input
          type="date"
          style={styles.input}
          value={occurredAt}
          onChange={(e) => setOccurredAt(e.target.value)}
        />

        <label style={styles.label}>Description</label>
        <textarea
          style={{ ...styles.input, minHeight: 60 }}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional notes..."
        />

        <label style={styles.label}>Tags (comma-separated)</label>
        <input
          style={styles.input}
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="groceries, weekly"
        />

        <div style={styles.actions}>
          <button style={styles.saveButton} onClick={handleSubmit} disabled={saving}>
            {saving ? 'Creating...' : 'Create Transaction'}
          </button>
          <button style={styles.cancelButton} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column' },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 18,
    color: tokens.colors.text,
    margin: '0 0 16px',
  },
  loading: {
    padding: 24,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
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
  actions: { display: 'flex', gap: 8, marginTop: 8 },
  saveButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: 'none',
    background: tokens.colors.accent,
    color: '#000',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  cancelButton: {
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    cursor: 'pointer',
  },
};
