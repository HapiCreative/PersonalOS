/**
 * AI Module — Section 5.5: Four AI modes.
 * Full-width layout (like Today View) with mode tabs:
 * Ask, Plan, Reflect, Improve.
 *
 * Uses violet accent (tokens.colors.violet) for AI/Derived elements.
 */

import { useState } from 'react';
import { tokens } from '../../styles/tokens';
import { AskMode } from './AskMode';
import { PlanMode } from './PlanMode';
import { ReflectMode } from './ReflectMode';
import { ImproveMode } from './ImproveMode';
import type { AIMode } from '../../types';

const MODE_TABS: { id: AIMode; label: string; description: string }[] = [
  { id: 'ask', label: 'Ask', description: 'Factual Q&A with citations from your knowledge base' },
  { id: 'plan', label: 'Plan', description: 'Create actionable plans based on your goals and tasks' },
  { id: 'reflect', label: 'Reflect', description: 'Find patterns and insights from your activity' },
  { id: 'improve', label: 'Improve', description: 'Get recommendations to improve your workflow' },
];

export function AIModule() {
  const [activeMode, setActiveMode] = useState<AIMode>('ask');

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>AI Assistant</h1>
        <p style={styles.subtitle}>
          {MODE_TABS.find((t) => t.id === activeMode)?.description}
        </p>
      </div>

      <div style={styles.tabs}>
        {MODE_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveMode(tab.id)}
            style={{
              ...styles.tab,
              color: activeMode === tab.id ? tokens.colors.violet : tokens.colors.textMuted,
              borderBottomColor: activeMode === tab.id ? tokens.colors.violet : 'transparent',
              background: activeMode === tab.id ? `${tokens.colors.violet}10` : 'transparent',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={styles.content}>
        {activeMode === 'ask' && <AskMode />}
        {activeMode === 'plan' && <PlanMode />}
        {activeMode === 'reflect' && <ReflectMode />}
        {activeMode === 'improve' && <ImproveMode />}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    width: '100%',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    background: tokens.colors.background,
    overflow: 'hidden',
  },
  header: {
    padding: '20px 24px 12px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 20,
    color: tokens.colors.text,
    margin: 0,
  },
  subtitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    margin: '4px 0 0',
  },
  tabs: {
    display: 'flex',
    gap: 0,
    borderBottom: `1px solid ${tokens.colors.border}`,
    paddingLeft: 24,
  },
  tab: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    padding: '10px 16px',
    border: 'none',
    borderBottom: '2px solid transparent',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  content: {
    flex: 1,
    overflow: 'auto',
  },
};
