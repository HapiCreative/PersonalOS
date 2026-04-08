/**
 * Finance: Account creation form.
 */

import { useState, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeAccountsApi } from '../../api/endpoints';
import type { AccountType } from '../../types';

const ACCOUNT_TYPES: { value: AccountType; label: string }[] = [
  { value: 'checking', label: 'Checking' },
  { value: 'savings', label: 'Savings' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'brokerage', label: 'Brokerage' },
  { value: 'crypto_wallet', label: 'Crypto Wallet' },
  { value: 'cash', label: 'Cash' },
  { value: 'loan', label: 'Loan' },
  { value: 'mortgage', label: 'Mortgage' },
  { value: 'other', label: 'Other' },
];

interface AccountCreateProps {
  onCreated: () => void;
  onCancel: () => void;
}

export function AccountCreate({ onCreated, onCancel }: AccountCreateProps) {
  const [title, setTitle] = useState('');
  const [accountType, setAccountType] = useState<AccountType>('checking');
  const [currency, setCurrency] = useState('USD');
  const [institution, setInstitution] = useState('');
  const [accountNumberMasked, setAccountNumberMasked] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    if (!title.trim()) {
      setError('Account name is required');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await financeAccountsApi.create({
        title: title.trim(),
        account_type: accountType,
        currency: currency.toUpperCase(),
        institution: institution.trim() || undefined,
        account_number_masked: accountNumberMasked.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      onCreated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [title, accountType, currency, institution, accountNumberMasked, notes, onCreated]);

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>New Account</h2>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.form}>
        <label style={styles.label}>Name *</label>
        <input
          style={styles.input}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Chase Checking"
          autoFocus
        />

        <label style={styles.label}>Type</label>
        <select
          style={styles.input}
          value={accountType}
          onChange={(e) => setAccountType(e.target.value as AccountType)}
        >
          {ACCOUNT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <label style={styles.label}>Currency</label>
        <input
          style={styles.input}
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          placeholder="USD"
          maxLength={3}
        />

        <label style={styles.label}>Institution</label>
        <input
          style={styles.input}
          value={institution}
          onChange={(e) => setInstitution(e.target.value)}
          placeholder="Bank/broker name"
        />

        <label style={styles.label}>Account # (last 4)</label>
        <input
          style={styles.input}
          value={accountNumberMasked}
          onChange={(e) => setAccountNumberMasked(e.target.value)}
          placeholder="1234"
          maxLength={4}
        />

        <label style={styles.label}>Notes</label>
        <textarea
          style={{ ...styles.input, minHeight: 60 }}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional notes..."
        />

        <div style={styles.actions}>
          <button style={styles.saveButton} onClick={handleSubmit} disabled={saving}>
            {saving ? 'Creating...' : 'Create Account'}
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
