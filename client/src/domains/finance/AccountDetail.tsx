/**
 * Finance: Account detail panel.
 * Shows metadata + transaction list filtered to account + balance history.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeAccountsApi, financeTransactionsApi, financeBalanceApi } from '../../api/endpoints';
import type {
  AccountResponse,
  AccountType,
  FinancialTransactionResponse,
  ComputedBalanceResponse,
  BalanceSnapshotResponse,
} from '../../types';

const ACCOUNT_TYPE_LABELS: Record<AccountType, string> = {
  checking: 'Checking',
  savings: 'Savings',
  credit_card: 'Credit Card',
  brokerage: 'Brokerage',
  crypto_wallet: 'Crypto',
  cash: 'Cash',
  loan: 'Loan',
  mortgage: 'Mortgage',
  other: 'Other',
};

interface AccountDetailProps {
  account: AccountResponse;
  onUpdated: () => void;
  onSelectTransaction: (tx: FinancialTransactionResponse) => void;
}

type DetailTab = 'info' | 'transactions' | 'balance';

export function AccountDetail({ account, onUpdated, onSelectTransaction }: AccountDetailProps) {
  const [tab, setTab] = useState<DetailTab>('info');
  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(account.title);
  const [editInstitution, setEditInstitution] = useState(account.institution || '');
  const [editNotes, setEditNotes] = useState(account.notes || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Transaction list for this account
  const [transactions, setTransactions] = useState<FinancialTransactionResponse[]>([]);
  const [txLoading, setTxLoading] = useState(false);

  // Balance info
  const [balance, setBalance] = useState<ComputedBalanceResponse | null>(null);
  const [snapshots, setSnapshots] = useState<BalanceSnapshotResponse[]>([]);
  const [balLoading, setBalLoading] = useState(false);

  useEffect(() => {
    setEditTitle(account.title);
    setEditInstitution(account.institution || '');
    setEditNotes(account.notes || '');
    setEditing(false);
  }, [account]);

  // Fetch transactions when tab switches
  useEffect(() => {
    if (tab === 'transactions') {
      setTxLoading(true);
      financeTransactionsApi.list({ account_id: account.node_id, limit: 50 })
        .then((res) => setTransactions(res.items))
        .catch(() => setTransactions([]))
        .finally(() => setTxLoading(false));
    }
  }, [tab, account.node_id]);

  // Fetch balance when tab switches
  useEffect(() => {
    if (tab === 'balance') {
      setBalLoading(true);
      Promise.all([
        financeAccountsApi.getBalance(account.node_id).catch(() => null),
        financeBalanceApi.listSnapshots(account.node_id).catch(() => ({ items: [], total: 0 })),
      ]).then(([bal, snaps]) => {
        setBalance(bal);
        setSnapshots(snaps.items);
      }).finally(() => setBalLoading(false));
    }
  }, [tab, account.node_id]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await financeAccountsApi.update(account.node_id, {
        title: editTitle,
        institution: editInstitution || undefined,
        notes: editNotes || undefined,
      });
      setEditing(false);
      onUpdated();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }, [account.node_id, editTitle, editInstitution, editNotes, onUpdated]);

  const handleDeactivate = useCallback(async () => {
    try {
      await financeAccountsApi.deactivate(account.node_id);
      onUpdated();
    } catch (e: any) {
      setError(e.message);
    }
  }, [account.node_id, onUpdated]);

  const formatAmount = (amount: string, currency: string) => {
    const num = parseFloat(amount);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(num);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>{account.title}</h2>
        <div style={styles.headerMeta}>
          <span style={styles.typeBadge}>{ACCOUNT_TYPE_LABELS[account.account_type]}</span>
          <span style={styles.currency}>{account.currency}</span>
          {!account.is_active && <span style={styles.inactiveBadge}>Inactive</span>}
        </div>
      </div>

      <div style={styles.tabs}>
        {(['info', 'transactions', 'balance'] as DetailTab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              ...styles.tab,
              color: tab === t ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: tab === t ? tokens.colors.accent : 'transparent',
            }}
          >
            {t === 'info' ? 'Info' : t === 'transactions' ? 'Transactions' : 'Balance'}
          </button>
        ))}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {tab === 'info' && (
        <div style={styles.section}>
          {editing ? (
            <div style={styles.form}>
              <label style={styles.label}>Name</label>
              <input
                style={styles.input}
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
              />
              <label style={styles.label}>Institution</label>
              <input
                style={styles.input}
                value={editInstitution}
                onChange={(e) => setEditInstitution(e.target.value)}
                placeholder="Bank/broker name"
              />
              <label style={styles.label}>Notes</label>
              <textarea
                style={{ ...styles.input, minHeight: 60 }}
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
              />
              <div style={styles.actions}>
                <button style={styles.saveButton} onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button style={styles.cancelButton} onClick={() => setEditing(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={styles.infoGrid}>
              <div style={styles.infoRow}>
                <span style={styles.infoLabel}>Institution</span>
                <span style={styles.infoValue}>{account.institution || '—'}</span>
              </div>
              <div style={styles.infoRow}>
                <span style={styles.infoLabel}>Account #</span>
                <span style={styles.infoValue}>
                  {account.account_number_masked ? `••••${account.account_number_masked}` : '—'}
                </span>
              </div>
              <div style={styles.infoRow}>
                <span style={styles.infoLabel}>Currency</span>
                <span style={styles.infoValue}>{account.currency}</span>
              </div>
              <div style={styles.infoRow}>
                <span style={styles.infoLabel}>Created</span>
                <span style={styles.infoValue}>{formatDate(account.created_at)}</span>
              </div>
              {account.notes && (
                <div style={styles.infoRow}>
                  <span style={styles.infoLabel}>Notes</span>
                  <span style={styles.infoValue}>{account.notes}</span>
                </div>
              )}
              <div style={styles.actions}>
                <button style={styles.editButton} onClick={() => setEditing(true)}>Edit</button>
                {account.is_active && (
                  <button style={styles.deactivateButton} onClick={handleDeactivate}>
                    Deactivate
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'transactions' && (
        <div style={styles.section}>
          {txLoading && <div style={styles.loadingText}>Loading transactions...</div>}
          {!txLoading && transactions.length === 0 && (
            <div style={styles.loadingText}>No transactions for this account</div>
          )}
          {transactions.map((tx) => (
            <button
              key={tx.id}
              onClick={() => onSelectTransaction(tx)}
              style={styles.txItem}
            >
              <div style={styles.txTop}>
                <span style={styles.txType}>{tx.transaction_type.replace(/_/g, ' ')}</span>
                <span style={{
                  ...styles.txAmount,
                  color: tx.signed_amount && parseFloat(tx.signed_amount) >= 0
                    ? tokens.colors.success
                    : tokens.colors.error,
                }}>
                  {formatAmount(tx.amount, tx.currency)}
                </span>
              </div>
              <div style={styles.txMeta}>
                <span style={styles.txDate}>{formatDate(tx.occurred_at)}</span>
                {tx.counterparty && <span style={styles.txCounterparty}>{tx.counterparty}</span>}
                <span style={{
                  ...styles.statusChip,
                  color: tx.status === 'pending' ? tokens.colors.warning
                    : tx.status === 'posted' ? tokens.colors.accent
                    : tokens.colors.success,
                }}>
                  {tx.status}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}

      {tab === 'balance' && (
        <div style={styles.section}>
          {balLoading && <div style={styles.loadingText}>Loading balance...</div>}
          {!balLoading && balance && (
            <div style={styles.balanceCard}>
              <div style={styles.balanceLabel}>Current Balance</div>
              <div style={styles.balanceValue}>{formatAmount(balance.balance, balance.currency)}</div>
              <div style={styles.balanceMeta}>
                {balance.is_computed ? 'Computed' : 'Reconciled'} as of {balance.as_of_date}
              </div>
            </div>
          )}
          {!balLoading && snapshots.length > 0 && (
            <>
              <h3 style={styles.subheading}>Snapshot History</h3>
              {snapshots.map((snap) => (
                <div key={snap.id} style={styles.snapshotRow}>
                  <span style={styles.snapshotDate}>{snap.snapshot_date}</span>
                  <span style={styles.snapshotBalance}>{formatAmount(snap.balance, snap.currency)}</span>
                  {snap.is_reconciled && <span style={styles.reconciledBadge}>Reconciled</span>}
                </div>
              ))}
            </>
          )}
          {!balLoading && !balance && snapshots.length === 0 && (
            <div style={styles.loadingText}>No balance data yet</div>
          )}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  header: { marginBottom: 16 },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 18,
    color: tokens.colors.text,
    margin: 0,
  },
  headerMeta: { display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 },
  typeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    borderRadius: tokens.radius,
    padding: '2px 6px',
  },
  currency: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  inactiveBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.warning,
    border: `1px solid ${tokens.colors.warning}`,
    borderRadius: tokens.radius,
    padding: '1px 5px',
  },
  tabs: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
    marginBottom: 16,
  },
  tab: {
    flex: 1,
    padding: '8px 10px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
    textAlign: 'center' as const,
  },
  error: {
    color: tokens.colors.error,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    padding: '8px 0',
  },
  section: { flex: 1, overflowY: 'auto' },
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
  deactivateButton: {
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.warning}`,
    background: 'none',
    color: tokens.colors.warning,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    cursor: 'pointer',
  },
  infoGrid: { display: 'flex', flexDirection: 'column', gap: 12 },
  infoRow: { display: 'flex', flexDirection: 'column', gap: 2 },
  infoLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  infoValue: { fontFamily: tokens.fonts.sans, fontSize: 14, color: tokens.colors.text },
  txItem: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    padding: '10px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
    textAlign: 'left' as const,
    gap: 4,
    background: 'none',
    border: 'none',
    borderBottomStyle: 'solid' as const,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border,
  },
  txTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  txType: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    textTransform: 'capitalize' as const,
  },
  txAmount: { fontFamily: tokens.fonts.mono, fontSize: 13, fontWeight: 600 },
  txMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  txDate: { fontFamily: tokens.fonts.mono, fontSize: 11, color: tokens.colors.textMuted },
  txCounterparty: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.textMuted,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  statusChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    textTransform: 'uppercase' as const,
  },
  loadingText: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
  },
  balanceCard: {
    padding: 16,
    background: tokens.colors.surface,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    marginBottom: 16,
  },
  balanceLabel: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  balanceValue: {
    fontFamily: tokens.fonts.mono,
    fontSize: 24,
    fontWeight: 600,
    color: tokens.colors.text,
    marginTop: 4,
  },
  balanceMeta: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    marginTop: 4,
  },
  subheading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
    margin: '16px 0 8px',
  },
  snapshotRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '8px 0',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  snapshotDate: { fontFamily: tokens.fonts.mono, fontSize: 12, color: tokens.colors.textMuted },
  snapshotBalance: { fontFamily: tokens.fonts.mono, fontSize: 13, color: tokens.colors.text, flex: 1 },
  reconciledBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.success,
    border: `1px solid ${tokens.colors.success}`,
    borderRadius: tokens.radius,
    padding: '1px 5px',
  },
};
