/**
 * Phase 10: Loading spinner component.
 * Consistent loading state across the application.
 */

import { tokens } from '../../styles/tokens';

interface LoadingSpinnerProps {
  size?: 'small' | 'medium' | 'large';
  message?: string;
}

const SIZES = {
  small: 16,
  medium: 24,
  large: 36,
};

export function LoadingSpinner({ size = 'medium', message }: LoadingSpinnerProps) {
  const px = SIZES[size];

  return (
    <div style={styles.container}>
      <div
        style={{
          ...styles.spinner,
          width: px,
          height: px,
          borderWidth: size === 'small' ? 2 : 3,
        }}
      />
      {message && <span style={styles.message}>{message}</span>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  spinner: {
    border: `3px solid ${tokens.colors.border}`,
    borderTopColor: tokens.colors.accent,
    borderRadius: '50%',
    animation: 'spin 0.8s linear infinite',
  },
  message: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
  },
};

// Inject keyframes (runs once)
if (typeof document !== 'undefined') {
  const styleEl = document.getElementById('pos-spinner-styles') || (() => {
    const el = document.createElement('style');
    el.id = 'pos-spinner-styles';
    el.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
    document.head.appendChild(el);
    return el;
  })();
}
