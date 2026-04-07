/**
 * Phase 10: Lazy loading wrapper for deferred component rendering.
 * Uses Intersection Observer to render components only when they enter the viewport.
 * Useful for context layer, enrichments, and other secondary content.
 */

import { useState, useEffect, useRef, type ReactNode } from 'react';
import { tokens } from '../../styles/tokens';

interface LazyLoadProps {
  children: ReactNode;
  placeholder?: ReactNode;
  rootMargin?: string;
  threshold?: number;
}

export function LazyLoad({
  children,
  placeholder,
  rootMargin = '100px',
  threshold = 0,
}: LazyLoadProps) {
  const [isVisible, setIsVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin, threshold }
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [rootMargin, threshold]);

  return (
    <div ref={ref}>
      {isVisible
        ? children
        : (placeholder || <div style={styles.placeholder} />)
      }
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  placeholder: {
    height: 40,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: tokens.colors.textMuted,
    fontSize: 12,
    fontFamily: tokens.fonts.sans,
  },
};
