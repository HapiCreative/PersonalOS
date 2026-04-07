/**
 * Phase 10: Custom hook for API request state management.
 * Provides consistent loading/error/data state across all modules.
 */

import { useState, useCallback } from 'react';

interface ApiRequestState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiRequestResult<T> extends ApiRequestState<T> {
  execute: (...args: any[]) => Promise<T | null>;
  reset: () => void;
}

export function useApiRequest<T>(
  apiCall: (...args: any[]) => Promise<T>
): UseApiRequestResult<T> {
  const [state, setState] = useState<ApiRequestState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (...args: any[]): Promise<T | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const result = await apiCall(...args);
        setState({ data: result, loading: false, error: null });
        return result;
      } catch (e: any) {
        const msg = e.message || 'An error occurred';
        setState({ data: null, loading: false, error: msg });
        return null;
      }
    },
    [apiCall]
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return { ...state, execute, reset };
}
