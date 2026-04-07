/**
 * Stale indicator component for list items (Phase 6).
 * Shows a warning badge when an item is stale.
 * Section 9.4: Warning color #F59E0B for stale/review items.
 */

import { tokens } from '../../styles/tokens';

interface StaleIndicatorProps {
  daysStale: number;
  prompt?: string;
}

export function StaleIndicator({ daysStale, prompt }: StaleIndicatorProps) {
  return (
    <span
      style={styles.badge}
      title={prompt || `Stale for ${daysStale} days`}
    >
      {daysStale}d
    </span>
  );
}

const styles: Record<string, React.CSSProperties> = {
  badge: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 10,
    color: tokens.colors.warning,
    padding: '1px 5px',
    border: `1px solid ${tokens.colors.warning}50`,
    borderRadius: tokens.radius,
    flexShrink: 0,
  },
};
