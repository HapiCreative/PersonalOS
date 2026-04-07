/**
 * Design tokens from Section 9.4.
 * All colors, radius, and typography definitions.
 */

export const tokens = {
  colors: {
    background: '#0A0A0B',
    surface: '#111113',
    border: '#27272A',
    text: '#D4D4D8',
    textMuted: '#71717A',
    accent: '#22D3EE',     // Cyan - active, user-created links
    violet: '#A78BFA',     // AI/Derived elements
    success: '#22C55E',    // Accepted, done
    warning: '#F59E0B',    // Stale, review
    error: '#EF4444',      // High priority, failures
  },
  radius: '4px',
  fonts: {
    sans: "'IBM Plex Sans', sans-serif",
    mono: "'IBM Plex Mono', monospace",
  },
  /** Section 9.1: Layout dimensions */
  layout: {
    railWidth: 48,
    listPaneWidth: 240,
    listPaneMinWidth: 180,
    listPaneMaxWidth: 400,
  },
} as const;

/**
 * Typography mapping from Section 9.3:
 * - Shell, nav labels: IBM Plex Sans 600
 * - Metadata, badges, IDs: IBM Plex Mono 400
 * - Tables, parameters, code: IBM Plex Mono
 * - KB / Journal reading: IBM Plex Sans 400
 * - Headings in detail: IBM Plex Sans 600
 */
