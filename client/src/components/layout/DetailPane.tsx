/**
 * Section 9.1: Detail Pane — Content area (top) + context layer (bottom).
 * Phase 5: Context layer implemented.
 *
 * Invariant U-03: Context layer hard cap of 8 items.
 * Invariant U-04: Per-category caps enforced.
 */

import { type ReactNode } from 'react';
import { tokens } from '../../styles/tokens';
import { ContextLayer } from '../context/ContextLayer';

interface DetailPaneProps {
  children: ReactNode;
  /** Node ID for context layer. When provided, the context layer is shown. */
  nodeId?: string;
  /** Callback when navigating to a related node from context layer */
  onNavigateToNode?: (nodeId: string, nodeType: string) => void;
}

export function DetailPane({ children, nodeId, onNavigateToNode }: DetailPaneProps) {
  return (
    <div style={styles.pane}>
      <div style={styles.content}>{children}</div>
      {nodeId && (
        <ContextLayer
          nodeId={nodeId}
          onNavigateToNode={onNavigateToNode}
        />
      )}
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
