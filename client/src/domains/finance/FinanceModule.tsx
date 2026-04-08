/**
 * Finance module: combines ListPane + DetailPane for financial entities.
 * Supports sub-views: accounts, transactions, categories, csv-import, balance-snapshot.
 * Section F1.5: Finance uses standard list/detail layout.
 */

import { useState, useCallback } from 'react';
import { ListPane } from '../../components/layout/ListPane';
import { DetailPane } from '../../components/layout/DetailPane';
import { AccountList } from './AccountList';
import { AccountDetail } from './AccountDetail';
import { AccountCreate } from './AccountCreate';
import { TransactionList } from './TransactionList';
import { TransactionDetail } from './TransactionDetail';
import { TransactionCreate } from './TransactionCreate';
import { CategoryManagement } from './CategoryManagement';
import { CsvImport } from './CsvImport';
import { BalanceSnapshotForm } from './BalanceSnapshotForm';
import { tokens } from '../../styles/tokens';
import type { AccountResponse, FinancialTransactionResponse } from '../../types';

type FinanceView = 'accounts' | 'transactions';
type DetailView =
  | { type: 'account-detail'; account: AccountResponse }
  | { type: 'account-create' }
  | { type: 'transaction-detail'; transaction: FinancialTransactionResponse }
  | { type: 'transaction-create' }
  | { type: 'categories' }
  | { type: 'csv-import' }
  | { type: 'balance-snapshot' }
  | null;

export function FinanceModule() {
  const [view, setView] = useState<FinanceView>('accounts');
  const [detailView, setDetailView] = useState<DetailView>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    setDetailView(null);
  }, []);

  const handleSelectAccount = useCallback((account: AccountResponse) => {
    setDetailView({ type: 'account-detail', account });
  }, []);

  const handleSelectTransaction = useCallback((tx: FinancialTransactionResponse) => {
    setDetailView({ type: 'transaction-detail', transaction: tx });
  }, []);

  // Get node ID for context layer based on current detail view
  const contextNodeId = detailView?.type === 'account-detail'
    ? detailView.account.node_id
    : undefined;

  return (
    <>
      <ListPane title="Finance">
        {/* Sub-view tabs */}
        <div style={styles.viewTabs}>
          <button
            onClick={() => { setView('accounts'); setDetailView(null); }}
            style={{
              ...styles.viewTab,
              color: view === 'accounts' ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: view === 'accounts' ? tokens.colors.accent : 'transparent',
            }}
          >
            Accounts
          </button>
          <button
            onClick={() => { setView('transactions'); setDetailView(null); }}
            style={{
              ...styles.viewTab,
              color: view === 'transactions' ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: view === 'transactions' ? tokens.colors.accent : 'transparent',
            }}
          >
            Transactions
          </button>
        </div>

        {/* Quick action buttons */}
        <div style={styles.quickActions}>
          <button
            style={styles.quickBtn}
            onClick={() => setDetailView({ type: 'categories' })}
            title="Manage categories"
          >
            Categories
          </button>
          <button
            style={styles.quickBtn}
            onClick={() => setDetailView({ type: 'csv-import' })}
            title="Import CSV"
          >
            Import
          </button>
          <button
            style={styles.quickBtn}
            onClick={() => setDetailView({ type: 'balance-snapshot' })}
            title="Record balance"
          >
            Balance
          </button>
        </div>

        {/* List content based on active view */}
        {view === 'accounts' && (
          <AccountList
            selectedId={
              detailView?.type === 'account-detail' ? detailView.account.node_id : null
            }
            onSelect={handleSelectAccount}
            onCreateNew={() => setDetailView({ type: 'account-create' })}
            refreshKey={refreshKey}
          />
        )}
        {view === 'transactions' && (
          <TransactionList
            selectedId={
              detailView?.type === 'transaction-detail' ? detailView.transaction.id : null
            }
            onSelect={handleSelectTransaction}
            onCreateNew={() => setDetailView({ type: 'transaction-create' })}
            refreshKey={refreshKey}
          />
        )}
      </ListPane>

      <DetailPane nodeId={contextNodeId}>
        {detailView?.type === 'account-create' ? (
          <AccountCreate onCreated={handleRefresh} onCancel={() => setDetailView(null)} />
        ) : detailView?.type === 'account-detail' ? (
          <AccountDetail
            account={detailView.account}
            onUpdated={handleRefresh}
            onSelectTransaction={handleSelectTransaction}
          />
        ) : detailView?.type === 'transaction-create' ? (
          <TransactionCreate onCreated={handleRefresh} onCancel={() => setDetailView(null)} />
        ) : detailView?.type === 'transaction-detail' ? (
          <TransactionDetail
            transaction={detailView.transaction}
            onUpdated={handleRefresh}
          />
        ) : detailView?.type === 'categories' ? (
          <CategoryManagement onClose={() => setDetailView(null)} />
        ) : detailView?.type === 'csv-import' ? (
          <CsvImport onClose={() => setDetailView(null)} onImported={handleRefresh} />
        ) : detailView?.type === 'balance-snapshot' ? (
          <BalanceSnapshotForm onClose={() => setDetailView(null)} onCreated={handleRefresh} />
        ) : (
          <div style={styles.placeholder}>
            <p style={styles.placeholderText}>
              Select an item or use the actions above
            </p>
          </div>
        )}
      </DetailPane>
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  viewTabs: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  viewTab: {
    flex: 1,
    padding: '10px 12px',
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 12,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
    textAlign: 'center' as const,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  quickActions: {
    display: 'flex',
    gap: 4,
    padding: '6px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  quickBtn: {
    flex: 1,
    padding: '4px 6px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 10,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    background: 'none',
    textAlign: 'center' as const,
  },
  placeholder: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    gap: 8,
  },
  placeholderText: {
    color: tokens.colors.textMuted,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
  },
};
