/**
 * Phase 10: Empty state component for consistent empty-list rendering.
 */

import { tokens } from '../../styles/tokens';

interface EmptyStateProps {
  icon?: string;
  title: string;
  message?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <div style={styles.container}>
      {icon && <div style={styles.icon}>{icon}</div>}
      <h3 style={styles.title}>{title}</h3>
      {message && <p style={styles.message}>{message}</p>}
      {action && (
        <button onClick={action.onClick} style={styles.actionButton}>
          {action.label}
        </button>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    gap: 8,
    textAlign: 'center',
  },
  icon: {
    fontSize: 32,
    marginBottom: 4,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    color: tokens.colors.text,
  },
  message: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    maxWidth: 300,
    lineHeight: 1.5,
  },
  actionButton: {
    marginTop: 8,
    padding: '6px 16px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.accent}`,
    background: 'none',
    color: tokens.colors.accent,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
};
