/**
 * Finance: Transaction list view with filters.
 * Filterable by account, date range, type, category, status, amount range.
 * State chips for pending/posted/settled/uncategorized.
 * Section F1.5.2.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { financeTransactionsApi, financeAccountsApi, financeCategoriesApi } from '../../api/endpoints';
import type {
  FinancialTransactionResponse,
  FinancialTransactionStatus,
  AccountResponse,
  FinancialCategoryResponse,
} from '../../types';

const STATUS_COLORS: Record<FinancialTransactionStatus, string> = {
  pending: tokens.colors.warning,
  posted: tokens.colors.accent,
  settled: tokens.colors.success,
};

interface TransactionListProps {
  selectedId: string | null;
  onSelect: (tx: FinancialTransactionResponse) => void;
  onCreateNew: () => void;
  refreshKey: number;
}

export function TransactionList({ selectedId, onSelect, onCreateNew, refreshKey }: TransactionListProps) {
  const [items, setItems] = useState<FinancialTransactionResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  // Filter state
  const [accountFilter, setAccountFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  // Reference data
  const [accounts, setAccounts] = useState<AccountResponse[]>([]);
  const [categories, setCategories] = useState<FinancialCategoryResponse[]>([]);

  // Load reference data
  useEffect(() => {
    financeAccountsApi.list({ limit: 100 }).then((res) => setAccounts(res.items)).catch(() => {});
    financeCategoriesApi.list().then((res) => setCategories(res.items)).catch(() => {});
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { limit: 50 };
      if (accountFilter) params.account_id = accountFilter;
      if (statusFilter) params.status = statusFilter;
      if (categoryFilter) params.category_id = categoryFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const res = await financeTransactionsApi.list(params);
      setItems(res.items);
      setTotal(res.total);
    } catch {
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [accountFilter, statusFilter, categoryFilter, dateFrom, dateTo]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems, refreshKey]);

  const formatAmount = (amount: string, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(parseFloat(amount));
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric',
    });
  };

  const getCategoryName = (catId: string | null) => {
    if (!catId) return null;
    const cat = categories.find((c) => c.id === catId);
    return cat?.name || null;
  };

  const getAccountName = (accountId: string) => {
    const acc = accounts.find((a) => a.node_id === accountId);
    return acc?.title || '';
  };

  return (
    <div style={styles.container}>
      <div style={styles.toolbar}>
        <button onClick={onCreateNew} style={styles.addButton}>
          + New Transaction
        </button>
      </div>

      <div style={styles.filterToggle}>
        <button
          onClick={() => setShowFilters(!showFilters)}
          style={styles.filterButton}
        >
          {showFilters ? 'Hide Filters' : 'Filters'} {total > 0 && `(${total})`}
        </button>
      </div>

      {showFilters && (
        <div style={styles.filters}>
          <select
            style={styles.filterInput}
            value={accountFilter}
            onChange={(e) => setAccountFilter(e.target.value)}
          >
            <option value="">All Accounts</option>
            {accounts.map((a) => (
              <option key={a.node_id} value={a.node_id}>{a.title}</option>
            ))}
          </select>
          <select
            style={styles.filterInput}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="posted">Posted</option>
            <option value="settled">Settled</option>
          </select>
          <select
            style={styles.filterInput}
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <input
            type="date"
            style={styles.filterInput}
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            placeholder="From"
          />
          <input
            type="date"
            style={styles.filterInput}
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            placeholder="To"
          />
        </div>
      )}

      <div style={styles.list}>
        {loading && <div style={styles.status}>Loading...</div>}
        {!loading && items.length === 0 && (
          <div style={styles.status}>No transactions found</div>
        )}
        {items.map((tx) => {
          const isInflow = tx.signed_amount && parseFloat(tx.signed_amount) >= 0;
          const catName = getCategoryName(tx.category_id);
          return (
            <button
              key={tx.id}
              onClick={() => onSelect(tx)}
              style={{
                ...styles.item,
                background: selectedId === tx.id ? `${tokens.colors.accent}15` : 'transparent',
                borderLeftColor: selectedId === tx.id ? tokens.colors.accent : 'transparent',
              }}
            >
              <div style={styles.itemTop}>
                <div style={styles.itemLeft}>
                  <span style={styles.itemTitle}>
                    {tx.counterparty || tx.description || tx.transaction_type.replace(/_/g, ' ')}
                  </span>
                  <div style={styles.itemMeta}>
                    <span style={styles.date}>{formatDate(tx.occurred_at)}</span>
                    <span style={styles.account}>{getAccountName(tx.account_id)}</span>
                    {catName && <span style={styles.category}>{catName}</span>}
                    {!tx.category_id && (
                      <span style={styles.uncategorized}>Uncategorized</span>
                    )}
                  </div>
                </div>
                <div style={styles.itemRight}>
                  <span style={{
                    ...styles.amount,
                    color: isInflow ? tokens.colors.success : tokens.colors.error,
                  }}>
                    {isInflow ? '+' : '-'}{formatAmount(tx.amount, tx.currency)}
                  </span>
                  <span style={{ ...styles.statusChip, color: STATUS_COLORS[tx.status] }}>
                    {tx.status}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
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
  filterToggle: {
    padding: '6px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  filterButton: {
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    color: tokens.colors.textMuted,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: 0,
  },
  filters: {
    padding: '8px 12px',
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  filterInput: {
    padding: '4px 6px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: tokens.colors.surface,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 11,
    outline: 'none',
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
    gap: 2,
    transition: 'background 0.1s',
    background: 'none',
  },
  itemTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  itemLeft: { flex: 1, minWidth: 0 },
  itemRight: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, flexShrink: 0 },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
    display: 'block',
    textTransform: 'capitalize' as const,
  },
  itemMeta: { display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' as const, marginTop: 2 },
  date: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.textMuted },
  account: { fontFamily: tokens.fonts.mono, fontSize: 10, color: tokens.colors.textMuted },
  category: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    background: `${tokens.colors.accent}10`,
    borderRadius: tokens.radius,
    padding: '0 4px',
  },
  uncategorized: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.warning,
  },
  amount: { fontFamily: tokens.fonts.mono, fontSize: 13, fontWeight: 600 },
  statusChip: {
    fontFamily: tokens.fonts.mono,
    fontSize: 9,
    textTransform: 'uppercase' as const,
  },
  status: {
    padding: 16,
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
    fontFamily: tokens.fonts.sans,
  },
};
