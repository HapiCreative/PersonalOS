/**
 * Phase 10: Virtualized list component for performance optimization.
 * Only renders visible items to reduce DOM overhead for long lists.
 * Used in list panes for tasks, KB entries, sources, etc.
 */

import { useState, useEffect, useRef, useCallback, type ReactNode } from 'react';
import { tokens } from '../../styles/tokens';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  renderItem: (item: T, index: number) => ReactNode;
  overscan?: number; // Extra items to render above/below viewport
  containerStyle?: React.CSSProperties;
}

export function VirtualizedList<T>({
  items,
  itemHeight,
  renderItem,
  overscan = 5,
  containerStyle,
}: VirtualizedListProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [containerHeight, setContainerHeight] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height);
      }
    });
    observer.observe(container);
    setContainerHeight(container.clientHeight);

    return () => observer.disconnect();
  }, []);

  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (container) {
      setScrollTop(container.scrollTop);
    }
  }, []);

  const totalHeight = items.length * itemHeight;
  const startIndex = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
  const endIndex = Math.min(
    items.length,
    Math.ceil((scrollTop + containerHeight) / itemHeight) + overscan
  );

  const visibleItems = items.slice(startIndex, endIndex);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{
        ...styles.container,
        ...containerStyle,
      }}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div
          style={{
            position: 'absolute',
            top: startIndex * itemHeight,
            left: 0,
            right: 0,
          }}
        >
          {visibleItems.map((item, localIndex) => (
            <div
              key={startIndex + localIndex}
              style={{ height: itemHeight }}
            >
              {renderItem(item, startIndex + localIndex)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    overflow: 'auto',
    flex: 1,
  },
};
