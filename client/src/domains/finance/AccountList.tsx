/**
 * Finance: Account list view.
 * Shows name, type, institution, current balance, active/inactive badge.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeAccountsApi } from '../../api/endpoints';
import type { AccountResponse, AccountType, ComputedBalanceResponse } from '../../types';

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

const FILTER_TABS: { label: string; value: boolean | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: true },
  { label: 'Inactive', value: false },
];

interface AccountListProps {
  selectedId: string | null;
  onSelect: (account: AccountResponse) => void;
  onCreateNew: () => void;
  refreshKey: number;
}

export function AccountList({ selectedId, onSelect, onCreateNew, refreshKey }: AccountListProps) {
  const [items, setItems] = useState<AccountResponse[]>([]);
  const [balances, setBalances] = useState<Record<string, ComputedBalanceResponse>>({});
  const [filter, setFilter] = useState<boolean | 'all'>('all');
  const [loading, setLoading] = useState(false);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: { is_active?: boolean } = {};
      if (filter !== 'all') params.is_active = filter;
      const res = await financeAccountsApi.list(params);
      setItems(res.items);
      // Fetch balances for all accounts
      const balanceResults: Record<string, ComputedBalanceResponse> = {};
      await Promise.all(
        res.items.map(async (account) => {
          try {
            const bal = await financeAccountsApi.getBalance(account.node_id);
            balanceResults[account.node_id] = bal;
          } catch {
            // Balance may not be computable yet
          }
        }),
      );
      setBalances(balanceResults);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  const formatBalance = (bal: ComputedBalanceResponse) => {
    const num = parseFloat(bal.balance);
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: bal.currency,
      minimumFractionDigits: 2,
    }).format(num);
  };

  return (
    <div style={styles.container}>
      <div style={styles.tabs}>
        {FILTER_TABS.map((tab) => (
          <button
            key={String(tab.value)}
            onClick={() => setFilter(tab.value)}
            style={{
              ...styles.tab,
              color: filter === tab.value ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: filter === tab.value ? tokens.colors.accent : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.toolbar}>
        <button onClick={onCreateNew} style={styles.addButton}>
          + New Account
        </button>
      </div>

      <div style={styles.list}>
        {loading && <div style={styles.status}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.status}>No accounts found</div>
        )}
        {items.map((account) => {
          const bal = balances[account.node_id];
          return (
            <button
              key={account.node_id}
              onClick={() => onSelect(account)}
              style={{
                ...styles.item,
                background: selectedId === account.node_id ? `${tokens.colors.accent}15` : 'transparent',
                borderLeftColor: selectedId === account.node_id ? tokens.colors.accent : 'transparent',
              }}
            >
              <div style={styles.itemTop}>
                <span style={styles.itemTitle}>{account.title}</span>
                {!account.is_active && <span style={styles.inactiveBadge}>Inactive</span>}
              </div>
              <div style={styles.itemMeta}>
                <span style={styles.typeBadge}>{ACCOUNT_TYPE_LABELS[account.account_type]}</span>
                {account.institution && (
                  <span style={styles.institution}>{account.institution}</span>
                )}
              </div>
              {bal && (
                <div style={styles.balance}>{formatBalance(bal)}</div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  tabs: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  tab: {
    flex: 1,
    padding: '8px 10px',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
    whiteSpace: 'nowrap' as const,
  },
  toolbar: { padding: '8px 12px', borderBottom: `1px solid ${tokens.colors.border}` },
  addButton: {
    width: '100%',
    padding: '6px 10px',
    borderRadius: tokens.radius,
    border: `1px dashed ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    color: tokens.colors.accent,
    cursor: 'pointer',
    background: 'none',
  },
  list: { flex: 1, overflowY: 'auto' },
  item: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    padding: '10px 16px',
    borderLeft: '2px solid transparent',
    borderBottom: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
    textAlign: 'left' as const,
    gap: 4,
    transition: 'background 0.1s',
    background: 'none',
  },
  itemTop: { display: 'flex', alignItems: 'center', gap: 8 },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    flex: 1,
  },
  inactiveBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.warning,
    border: `1px solid ${tokens.colors.warning}`,
    borderRadius: tokens.radius,
    padding: '1px 5px',
  },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 8 },
  typeBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}15`,
    borderRadius: tokens.radius,
    padding: '1px 5px',
  },
  institution: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  balance: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.text,
    fontWeight: 600,
  },
  status: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
  },
};
