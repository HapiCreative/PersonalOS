/**
 * Section 9.1: List Pane (240px, resizable).
 * Filtered Core entity list with resizer handle.
 */

import { useState, useCallback, useRef, useEffect, type ReactNode } from 'react';
import { tokens } from '../../styles/tokens';

interface ListPaneProps {
  children: ReactNode;
  title: string;
}

export function ListPane({ children, title }: ListPaneProps) {
  const [width, setWidth] = useState(tokens.layout.listPaneWidth);
  const isResizing = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    isResizing.current = true;
    startX.current = e.clientX;
    startWidth.current = width;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [width]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const delta = e.clientX - startX.current;
      const newWidth = Math.max(
        tokens.layout.listPaneMinWidth,
        Math.min(tokens.layout.listPaneMaxWidth, startWidth.current + delta),
      );
      setWidth(newWidth);
    };

    const onMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  return (
    <div style={{ ...styles.pane, width }}>
      <div style={styles.header}>
        <h2 style={styles.title}>{title}</h2>
      </div>
      <div style={styles.content}>{children}</div>
      <div style={styles.resizer} onMouseDown={onMouseDown} />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  pane: {
    height: '100%',
    background: tokens.colors.surface,
    borderRight: `1px solid ${tokens.colors.border}`,
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    flexShrink: 0,
  },
  header: {
    padding: '12px 16px',
    borderBottom: `1px solid ${tokens.colors.border}`,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 13,
    color: tokens.colors.textMuted,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.5px',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
  },
  resizer: {
    position: 'absolute',
    right: -2,
    top: 0,
    bottom: 0,
    width: 4,
    cursor: 'col-resize',
    zIndex: 10,
  },
};
