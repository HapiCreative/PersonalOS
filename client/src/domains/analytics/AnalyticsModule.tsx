/**
 * Analytics module: full-width behavioral surface for analytics dashboard.
 * Section 4.7: Three-layer analytics dashboard:
 *   1. Execution Dashboard (primary, default view)
 *   2. Strategic Alignment (secondary, tab)
 *   3. Wellbeing Patterns (tertiary, overlay toggle)
 *
 * Invariant D-04: All analytics outputs explicitly classified as
 * descriptive / correlational / recommendation.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { ExecutionDashboard } from './ExecutionDashboard';
import { StrategicAlignment } from './StrategicAlignment';
import { WellbeingPatterns } from './WellbeingPatterns';
import { SemanticClusters } from './SemanticClusters';

type AnalyticsTab = 'execution' | 'strategic' | 'wellbeing' | 'clusters';

export function AnalyticsModule() {
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('execution');

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2 style={styles.title}>Analytics</h2>
        <div style={styles.tabBar}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                ...styles.tab,
                color: activeTab === tab.id ? tokens.colors.accent : tokens.colors.textMuted,
                borderBottomColor: activeTab === tab.id ? tokens.colors.accent : 'transparent',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div style={styles.content}>
        {activeTab === 'execution' && <ExecutionDashboard />}
        {activeTab === 'strategic' && <StrategicAlignment />}
        {activeTab === 'wellbeing' && <WellbeingPatterns />}
        {activeTab === 'clusters' && <SemanticClusters />}
      </div>
    </div>
  );
}

const tabs: { id: AnalyticsTab; label: string }[] = [
  { id: 'execution', label: 'Execution' },
  { id: 'strategic', label: 'Strategic Alignment' },
  { id: 'wellbeing', label: 'Wellbeing Patterns' },
  { id: 'clusters', label: 'Topic Clusters' },
];

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  header: {
    padding: '16px 24px 0',
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontSize: 20,
    fontWeight: 600,
    color: tokens.colors.text,
    margin: '0 0 12px',
  },
  tabBar: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  tab: {
    padding: '10px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 600,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px 24px',
  },
};
