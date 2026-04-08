/**
 * Finance: Balance snapshot form.
 * Account, balance, date, reconciliation checkbox.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeAccountsApi, financeBalanceApi } from '../../api/endpoints';
import type { AccountResponse } from '../../types';

interface BalanceSnapshotFormProps {
  onClose: () => void;
  onCreated: () => void;
  preselectedAccountId?: string;
}

export function BalanceSnapshotForm({ onClose, onCreated, preselectedAccountId }: BalanceSnapshotFormProps) {
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [accountId, setAccountId] = useState(preselectedAccountId || '');
  const [balance, setBalance] = useState('');
  const [snapshotDate, setSnapshotDate] = useState(
    new Date().toISOString().split('T')[0]
  );
  const [isReconciled, setIsReconciled] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    financeAccountsApi.list({ is_active: true, limit: 100 })
      .then((res) => {
        setAccounts(res.items);
        if (!preselectedAccountId && res.items.length > 0) {
          setAccountId(res.items[0].node_id);
        }
      })
      .catch(() => {});
  }, [preselectedAccountId]);

  const handleSubmit = useCallback(async () => {
    if (!accountId) {
      setError('Please select an account');
      return;
    }
    const bal = parseFloat(balance);
    if (isNaN(bal)) {
      setError('Balance must be a valid number');
      return;
    }
    if (!snapshotDate) {
      setError('Date is required');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const account = accounts.find((a) => a.node_id === accountId);
      await financeBalanceApi.createSnapshot({
        account_id: accountId,
        balance: bal,
        currency: account?.currency || 'USD',
        snapshot_date: snapshotDate,
        source: 'manual',
        is_reconciled: isReconciled,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [accountId, balance, snapshotDate, isReconciled, accounts, onCreated]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.heading}>New Balance Snapshot</h2>
        <button style={styles.closeButton} onClick={onClose}>Back</button>
      </div>

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
            <option key={a.node_id} value={a.node_id}>{a.title} ({a.currency})</option>
          ))}
        </select>

        <label style={styles.label}>Balance *</label>
        <input
          style={styles.input}
          value={balance}
          onChange={(e) => setBalance(e.target.value)}
          type="number"
          step="0.01"
          placeholder="0.00"
          autoFocus
        />

        <label style={styles.label}>Snapshot Date *</label>
        <input
          type="date"
          style={styles.input}
          value={snapshotDate}
          onChange={(e) => setSnapshotDate(e.target.value)}
        />

        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={isReconciled}
            onChange={(e) => setIsReconciled(e.target.checked)}
          />
          <span style={styles.checkboxLabel}>
            Mark as reconciled (Invariant F-09: reconciled snapshots are authoritative)
          </span>
        </label>

        <div style={styles.actions}>
          <button style={styles.saveButton} onClick={handleSubmit} disabled={saving}>
            {saving ? 'Creating...' : 'Create Snapshot'}
          </button>
          <button style={styles.cancelButton} onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column' },
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
  },
  checkboxRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    cursor: 'pointer',
    marginTop: 4,
  },
  checkboxLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
  },
  actions: { display: 'flex', gap: 8, marginTop: 12 },
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
