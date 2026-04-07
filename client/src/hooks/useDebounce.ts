/**
 * Phase 10: Debounce hook for search and input performance.
 * Prevents excessive API calls when typing.
 */

import { useState, useEffect } from 'react';

export function useDebounce<T>(value: T, delayMs: number = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
