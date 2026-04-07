/**
 * Review module: full-width behavioral surface for weekly/monthly reviews.
 * Section 5.5: Weekly and Monthly review workflows.
 * Uses full-width layout like TodayView (no list/detail split).
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { WeeklyReview } from './WeeklyReview';
import { MonthlyReview } from './MonthlyReview';

type ReviewTab = 'weekly' | 'monthly';

export function ReviewModule() {
  const [activeTab, setActiveTab] = useState<ReviewTab>('weekly');

  return (
    <div style={styles.container}>
      <div style={styles.tabBar}>
        <button
          onClick={() => setActiveTab('weekly')}
          style={{
            ...styles.tab,
            color: activeTab === 'weekly' ? tokens.colors.accent : tokens.colors.textMuted,
            borderBottomColor: activeTab === 'weekly' ? tokens.colors.accent : 'transparent',
          }}
        >
          Weekly Review
        </button>
        <button
          onClick={() => setActiveTab('monthly')}
          style={{
            ...styles.tab,
            color: activeTab === 'monthly' ? tokens.colors.accent : tokens.colors.textMuted,
            borderBottomColor: activeTab === 'monthly' ? tokens.colors.accent : 'transparent',
          }}
        >
          Monthly Review
        </button>
      </div>
      <div style={styles.content}>
        {activeTab === 'weekly' ? <WeeklyReview /> : <MonthlyReview />}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  tabBar: {
    display: 'flex',
    borderBottom: `1px solid ${tokens.colors.border}`,
    padding: '0 24px',
  },
  tab: {
    padding: '12px 16px',
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    fontWeight: 600,
    border: 'none',
    borderBottom: '2px solid transparent',
    background: 'none',
    cursor: 'pointer',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px 0',
  },
};
