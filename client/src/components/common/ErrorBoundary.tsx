/**
 * Phase 10: Error boundary component.
 * Catches React rendering errors and shows a user-friendly fallback.
 */

import { Component, type ReactNode, type ErrorInfo } from 'react';
import { tokens } from '../../styles/tokens';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo);
    this.props.onError?.(error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div style={styles.container}>
          <div style={styles.icon}>!</div>
          <h3 style={styles.title}>Something went wrong</h3>
          <p style={styles.message}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={styles.retryButton}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
    gap: 12,
    textAlign: 'center',
  },
  icon: {
    width: 40,
    height: 40,
    borderRadius: '50%',
    background: `${tokens.colors.error}20`,
    color: tokens.colors.error,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: tokens.fonts.sans,
    fontWeight: 700,
    fontSize: 20,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 16,
    color: tokens.colors.text,
  },
  message: {
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    color: tokens.colors.textMuted,
    maxWidth: 400,
    lineHeight: 1.5,
  },
  retryButton: {
    marginTop: 8,
    padding: '8px 20px',
    borderRadius: tokens.radius,
    border: `1px solid ${tokens.colors.border}`,
    background: 'none',
    color: tokens.colors.accent,
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
};
