/**
 * Section 9.1: Detail Pane — Content area (top) + context layer (bottom).
 * Context layer implemented in Phase 5.
 */

import { type ReactNode } from 'react';
import { tokens } from '../../styles/tokens';

interface DetailPaneProps {
  children: ReactNode;
}

export function DetailPane({ children }: DetailPaneProps) {
  return (
    <div style={styles.pane}>
      <div style={styles.content}>{children}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  pane: {
    flex: 1,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    background: tokens.colors.background,
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    padding: 24,
  },
};
