/**
 * Phase 10: Settings/Admin module.
 * Export/import UI, retention stats, cache refresh, batch embedding.
 * Section 1.1: Core entities are exportable.
 * Section 1.7: User-owned data — always exportable.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { ExportImportPanel } from './ExportImportPanel';
import { RetentionPanel } from './RetentionPanel';
import { SystemPanel } from './SystemPanel';

type SettingsTab = 'export' | 'retention' | 'system';

const TABS: { id: SettingsTab; label: string }[] = [
  { id: 'export', label: 'Export / Import' },
  { id: 'retention', label: 'Retention' },
  { id: 'system', label: 'System' },
];

export function SettingsModule() {
  const [tab, setTab] = useState<SettingsTab>('export');

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Settings</h1>
      </div>

      <div style={styles.tabs}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              ...styles.tab,
              color: tab === t.id ? tokens.colors.accent : tokens.colors.textMuted,
              borderBottomColor: tab === t.id ? tokens.colors.accent : 'transparent',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div style={styles.content}>
        {tab === 'export' && <ExportImportPanel />}
        {tab === 'retention' && <RetentionPanel />}
        {tab === 'system' && <SystemPanel />}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    width: '100%',
    maxWidth: 800,
    margin: '0 auto',
    padding: '24px 32px',
    overflow: 'auto',
  },
  header: {
    marginBottom: 16,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
  },
  tabs: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
    marginBottom: 24,
  },
  tab: {
    padding: '10px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
  },
  content: {
    flex: 1,
  },
};
