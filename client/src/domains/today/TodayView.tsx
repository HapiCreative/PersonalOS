/**
 * Today View: Full-width behavioral surface (Section 5.1, 9.1).
 * No list/detail split — uses the full main area.
 *
 * 4-stage daily cycle: commit -> execute -> reflect -> learn
 *
 * Invariant U-02: Hard cap of 10 items enforced by backend.
 * Invariant U-04: Per-section caps enforced by backend.
 * Invariant U-01: Max 2 unsolicited intelligence items.
 * Invariant U-05: Suppression precedence applied by backend.
 */

import { useState, useEffect, useCallback } from 'react';
import { tokens } from '../../styles/tokens';
import { todayApi } from '../../api/endpoints';
import type { TodayViewResponse, TodaySectionResponse, TodayItemResponse } from '../../types';

const SECTION_LABELS: Record<string, string> = {
  focus: 'In Focus',
  due: 'Due & Overdue',
  habits: 'Habits',
  learning: 'Learning',
  goal_nudges: 'Goal Nudges',
  review: 'Review',
  resurfaced: 'Resurfaced',
  journal: 'Journal',
};

const SECTION_ICONS: Record<string, string> = {
  focus: '▸',
  due: '!',
  habits: '↻',
  learning: '◈',
  goal_nudges: '◎',
  review: '◇',
  resurfaced: '↗',
  journal: '✎',
};

const STAGE_LABELS: Record<string, string> = {
  commit: 'Morning Commit',
  execute: 'Execute',
  reflect: 'Evening Reflect',
  learn: 'Learn',
};

const STAGE_COLORS: Record<string, string> = {
  commit: tokens.colors.accent,
  execute: tokens.colors.success,
  reflect: tokens.colors.violet,
  learn: tokens.colors.warning,
};

interface TodayViewProps {
  onNavigate?: (module: string) => void;
}

export function TodayView({ onNavigate }: TodayViewProps) {
  const [data, setData] = useState<TodayViewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await todayApi.get();
      setData(result);
    } catch (e: any) {
      setError(e.message || 'Failed to load Today View');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div style={styles.fullWidth}>
        <div style={styles.loadingState}>Loading Today View...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.fullWidth}>
        <div style={styles.errorState}>
          <p>{error}</p>
          <button onClick={fetchData} style={styles.retryButton}>Retry</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div style={styles.fullWidth}>
      <div style={styles.container}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerTop}>
            <h1 style={styles.heading}>Today</h1>
            <span style={styles.dateLabel}>
              {new Date(data.date).toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </span>
          </div>

          {/* Daily cycle stage indicator */}
          <div style={styles.stageRow}>
            {['commit', 'execute', 'reflect', 'learn'].map((stage) => (
              <div
                key={stage}
                style={{
                  ...styles.stageChip,
                  background: data.stage === stage ? `${STAGE_COLORS[stage]}20` : 'transparent',
                  borderColor: data.stage === stage ? STAGE_COLORS[stage] : tokens.colors.border,
                  color: data.stage === stage ? STAGE_COLORS[stage] : tokens.colors.textMuted,
                }}
              >
                {STAGE_LABELS[stage]}
              </div>
            ))}
          </div>

          <div style={styles.itemCount}>
            {data.total_count} items today
            {/* Invariant U-02: Backend enforces max 10 */}
          </div>
        </div>

        {/* Sections */}
        {data.sections.length === 0 ? (
          <div style={styles.emptyState}>
            <p style={styles.emptyTitle}>All clear!</p>
            <p style={styles.emptySubtitle}>No items need your attention right now.</p>
          </div>
        ) : (
          <div style={styles.sectionsContainer}>
            {data.sections.map((section) => (
              <TodaySection
                key={section.name}
                section={section}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TodaySection({ section, onNavigate }: { section: TodaySectionResponse; onNavigate?: (module: string) => void }) {
  const label = SECTION_LABELS[section.name] || section.name;
  const icon = SECTION_ICONS[section.name] || '●';

  return (
    <div style={styles.section}>
      <div style={styles.sectionHeader}>
        <span style={styles.sectionIcon}>{icon}</span>
        <h2 style={styles.sectionTitle}>{label}</h2>
        <span style={styles.sectionCount}>{section.items.length}</span>
      </div>
      <div style={styles.sectionItems}>
        {section.items.map((item, idx) => (
          <TodayItemCard key={`${item.node_id || idx}`} item={item} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  );
}

function TodayItemCard({ item, onNavigate }: { item: TodayItemResponse; onNavigate?: (module: string) => void }) {
  const handleClick = () => {
    if (!onNavigate || !item.node_id) return;
    // Navigate to the appropriate module based on item_type
    if (item.item_type === 'task') {
      onNavigate('tasks');
    } else if (item.item_type === 'goal_nudge') {
      onNavigate('goals');
    } else if (item.item_type === 'journal_prompt') {
      onNavigate('journal');
    }
  };

  const isOverdue = item.metadata?.overdue === true;

  return (
    <button
      onClick={handleClick}
      style={{
        ...styles.itemCard,
        borderLeftColor: item.priority === 'urgent' ? tokens.colors.error
          : item.priority === 'high' ? tokens.colors.warning
          : isOverdue ? tokens.colors.error
          : item.item_type === 'goal_nudge' ? tokens.colors.violet
          : item.item_type === 'journal_prompt' ? tokens.colors.accent
          : tokens.colors.border,
      }}
    >
      <div style={styles.itemCardTop}>
        <span style={styles.itemTitle}>{item.title}</span>
        {item.is_unsolicited && (
          <span style={styles.unsolicitedBadge} title="Invariant U-01: System suggestion">
            AI
          </span>
        )}
      </div>
      {item.subtitle && (
        <span style={{
          ...styles.itemSubtitle,
          color: isOverdue ? tokens.colors.error : tokens.colors.textMuted,
        }}>
          {item.subtitle}
        </span>
      )}
      {item.progress !== null && item.progress !== undefined && (
        <div style={styles.itemProgressBar}>
          <div style={{
            ...styles.itemProgressFill,
            width: `${Math.round(item.progress * 100)}%`,
          }} />
        </div>
      )}
    </button>
  );
}

const styles: Record<string, React.CSSProperties> = {
  fullWidth: {
    flex: 1,
    height: '100%',
    overflowY: 'auto',
    background: tokens.colors.background,
  },
  container: {
    maxWidth: 640,
    margin: '0 auto',
    padding: '24px 20px',
  },
  loadingState: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
  },
  errorState: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    gap: 12,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.error,
  },
  retryButton: {
    padding: '6px 14px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    cursor: 'pointer',
    background: 'none',
  },
  header: {
    marginBottom: 28,
  },
  headerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 12,
  },
  heading: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
    margin: 0,
  },
  dateLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 13,
    color: tokens.colors.textMuted,
  },
  stageRow: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  },
  stageChip: {
    padding: '4px 10px',
    borderRadius: tokens.radius,
    border: '1px solid',
    fontFamily: tokens.fonts.sans,
    fontSize: 12,
    fontWeight: 500,
  },
  itemCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 12,
    color: tokens.colors.textMuted,
  },
  emptyState: {
    textAlign: 'center' as const,
    padding: '48px 0',
  },
  emptyTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 18,
    fontWeight: 600,
    color: tokens.colors.text,
    marginBottom: 8,
  },
  emptySubtitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
    color: tokens.colors.textMuted,
  },
  sectionsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
  },
  section: {
    background: tokens.colors.surface,
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    overflow: 'hidden',
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '10px 14px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  sectionIcon: {
    fontFamily: tokens.fonts.mono,
    fontSize: 14,
    color: tokens.colors.accent,
    width: 18,
    textAlign: 'center' as const,
  },
  sectionTitle: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.text,
    flex: 1,
    margin: 0,
  },
  sectionCount: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    padding: '2px 6px',
    background: `${tokens.colors.textMuted}15`,
    borderRadius: tokens.radius,
  },
  sectionItems: {
    display: 'flex',
    flexDirection: 'column',
  },
  itemCard: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    padding: '10px 14px',
    borderLeft: '3px solid',
    borderBottom: `1px solid ${tokens.colors.border}`,
    cursor: 'pointer',
    textAlign: 'left' as const,
    gap: 4,
    transition: 'background 0.1s',
    background: 'none',
  },
  itemCardTop: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  itemTitle: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.text,
    flex: 1,
  },
  unsolicitedBadge: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.violet,
    padding: '1px 5px',
    border: `1px solid ${tokens.colors.violet}`,
    borderRadius: tokens.radius,
    flexShrink: 0,
  },
  itemSubtitle: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
  itemProgressBar: {
    width: '100%',
    height: 3,
    background: tokens.colors.border,
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: 4,
  },
  itemProgressFill: {
    height: '100%',
    background: tokens.colors.accent,
    borderRadius: 2,
    transition: 'width 0.3s ease',
  },
};
