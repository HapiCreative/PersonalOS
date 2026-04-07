/**
 * Cmd+K Modal (Section 5.4):
 * - Search mode (default): type to search Core entities
 * - Capture mode (Tab or >): type anything, Enter to save as inbox_item
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { tokens } from '../styles/tokens';
import { searchApi, inboxApi } from '../api/endpoints';
import type { NodeResponse, SearchResultItem } from '../types';

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelectNode?: (node: NodeResponse) => void;
}

export function CommandPalette({ open, onClose, onSelectNode }: CommandPaletteProps) {
  const [mode, setMode] = useState<'search' | 'capture'>('search');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [captureSuccess, setCaptureSuccess] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
      setMode('search');
      setCaptureSuccess(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Debounced search
  useEffect(() => {
    if (mode !== 'search' || !query.trim()) {
      setResults([]);
      return;
    }

    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await searchApi.search(query, { limit: 8 });
        setResults(res.items);
        setSelectedIndex(0);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);

    return () => clearTimeout(debounceRef.current);
  }, [query, mode]);

  const handleInputChange = useCallback((value: string) => {
    setCaptureSuccess(false);
    // Switch to capture mode if starts with >
    if (value.startsWith('>') && mode === 'search') {
      setMode('capture');
      setQuery(value.slice(1).trimStart());
      return;
    }
    setQuery(value);
  }, [mode]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
      return;
    }

    // Tab toggles between search and capture mode
    if (e.key === 'Tab') {
      e.preventDefault();
      setMode((m) => (m === 'search' ? 'capture' : 'search'));
      return;
    }

    if (mode === 'search') {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[selectedIndex]) {
        e.preventDefault();
        onSelectNode?.(results[selectedIndex].node);
        onClose();
      }
    } else if (mode === 'capture' && e.key === 'Enter' && query.trim()) {
      e.preventDefault();
      handleCapture();
    }
  }, [mode, results, selectedIndex, query, onClose, onSelectNode]);

  const handleCapture = async () => {
    if (!query.trim()) return;
    try {
      await inboxApi.create(query.trim());
      setCaptureSuccess(true);
      setQuery('');
      setTimeout(() => onClose(), 600);
    } catch {
      // Error handling
    }
  };

  if (!open) return null;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.inputRow}>
          <span style={styles.modeIndicator}>
            {mode === 'search' ? '/' : '>'}
          </span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === 'search' ? 'Search nodes...' : 'Quick capture to inbox...'}
            style={styles.input}
          />
          <span style={styles.modeLabel}>
            {mode === 'search' ? 'Search' : 'Capture'}
          </span>
        </div>

        {captureSuccess && (
          <div style={styles.successMsg}>Captured to inbox</div>
        )}

        {mode === 'search' && results.length > 0 && (
          <div style={styles.results}>
            {results.map((item, i) => (
              <button
                key={item.node.id}
                style={{
                  ...styles.resultItem,
                  background: i === selectedIndex ? `${tokens.colors.accent}15` : 'transparent',
                }}
                onClick={() => {
                  onSelectNode?.(item.node);
                  onClose();
                }}
                onMouseEnter={() => setSelectedIndex(i)}
              >
                <span style={styles.resultType}>{item.node.type}</span>
                <span style={styles.resultTitle}>{item.node.title}</span>
                {/* Phase 5: Signal score display in search results */}
                {item.signal_score !== null && item.signal_score !== undefined && (
                  <span style={styles.signalScore}>
                    {item.signal_score.toFixed(2)}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {mode === 'search' && query && !loading && results.length === 0 && (
          <div style={styles.empty}>No results. Press Tab to capture instead.</div>
        )}

        <div style={styles.footer}>
          <span style={styles.hint}>Tab to switch mode</span>
          <span style={styles.hint}>Esc to close</span>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    paddingTop: '20vh',
    zIndex: 1000,
  },
  modal: {
    width: 520,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    overflow: 'hidden',
    boxShadow: '0 16px 48px rgba(0,0,0,0.5)',
  },
  inputRow: {
    display: 'flex',
    alignItems: 'center',
    padding: '12px 16px',
    borderBottom: `1px solid ${tokens.colors.border}`,
    gap: 8,
  },
  modeIndicator: {
    fontFamily: tokens.fonts.mono,
    fontSize: 16,
    color: tokens.colors.accent,
    fontWeight: 500,
    width: 16,
    textAlign: 'center' as const,
  },
  input: {
    flex: 1,
    background: 'none',
    border: 'none',
    outline: 'none',
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 15,
    padding: 0,
  },
  modeLabel: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    padding: '2px 6px',
    background: tokens.colors.background,
    borderRadius: tokens.radius,
  },
  results: {
    maxHeight: 300,
    overflowY: 'auto',
  },
  resultItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    width: '100%',
    padding: '8px 16px',
    border: 'none',
    cursor: 'pointer',
    textAlign: 'left' as const,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
  },
  resultType: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
    minWidth: 70,
  },
  resultTitle: {
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap' as const,
  },
  signalScore: {
    fontFamily: tokens.fonts.mono,
    fontSize: 10,
    color: tokens.colors.accent,
    padding: '1px 4px',
    background: `${tokens.colors.accent}15`,
    borderRadius: '2px',
    flexShrink: 0,
  },
  empty: {
    padding: '16px',
    color: tokens.colors.textMuted,
    fontSize: 13,
    textAlign: 'center' as const,
  },
  successMsg: {
    padding: '10px 16px',
    color: tokens.colors.success,
    fontSize: 13,
    fontFamily: tokens.fonts.sans,
    textAlign: 'center' as const,
  },
  footer: {
    display: 'flex',
    justifyContent: 'center',
    gap: 16,
    padding: '8px 16px',
    borderTop: `1px solid ${tokens.colors.border}`,
  },
  hint: {
    fontFamily: tokens.fonts.mono,
    fontSize: 11,
    color: tokens.colors.textMuted,
  },
};
