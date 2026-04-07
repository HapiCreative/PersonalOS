/**
 * Section 9.1: Rail (48px) — Icon nav with cyan accent for active state.
 * Typography: Shell, nav labels use IBM Plex Sans 600.
 */

import { tokens } from '../../styles/tokens';
import {
  Inbox,
  Sun,
  CheckSquare,
  BookOpen,
  Target,
  FileText,
  Brain,
  Search,
  Layout,
  Trash2,
  LogOut,
  FolderKanban,
  ClipboardList,
  Sparkles,
  Settings,
} from 'lucide-react';

export type NavModule = 'today' | 'inbox' | 'tasks' | 'journal' | 'goals' | 'projects' | 'kb' | 'sources' | 'memory' | 'review' | 'templates' | 'cleanup' | 'ai' | 'settings';

interface RailProps {
  active: NavModule;
  onNavigate: (module: NavModule) => void;
  onLogout: () => void;
}

const navItems: { id: NavModule; icon: typeof Inbox; label: string }[] = [
  { id: 'today', icon: Sun, label: 'Today' },
  { id: 'inbox', icon: Inbox, label: 'Inbox' },
  { id: 'tasks', icon: CheckSquare, label: 'Tasks' },
  { id: 'journal', icon: BookOpen, label: 'Journal' },
  { id: 'goals', icon: Target, label: 'Goals' },
  { id: 'projects', icon: FolderKanban, label: 'Projects' },
  { id: 'kb', icon: FileText, label: 'KB' },
  { id: 'sources', icon: Search, label: 'Sources' },
  { id: 'memory', icon: Brain, label: 'Memory' },
  { id: 'ai', icon: Sparkles, label: 'AI' },
  { id: 'review', icon: ClipboardList, label: 'Review' },
  { id: 'cleanup', icon: Trash2, label: 'Cleanup' },
  { id: 'templates', icon: Layout, label: 'Templates' },
  { id: 'settings', icon: Settings, label: 'Settings' },
];

export function Rail({ active, onNavigate, onLogout }: RailProps) {
  return (
    <nav style={styles.rail}>
      <div style={styles.navGroup}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              style={{
                ...styles.navButton,
                color: isActive ? tokens.colors.accent : tokens.colors.textMuted,
                background: isActive ? `${tokens.colors.accent}15` : 'transparent',
              }}
              title={item.label}
            >
              <Icon size={20} strokeWidth={isActive ? 2 : 1.5} />
            </button>
          );
        })}
      </div>
      <div style={styles.bottomGroup}>
        <button onClick={onLogout} style={styles.navButton} title="Logout">
          <LogOut size={20} strokeWidth={1.5} />
        </button>
      </div>
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  rail: {
    width: tokens.layout.railWidth,
    minWidth: tokens.layout.railWidth,
    height: '100%',
    background: tokens.colors.surface,
    borderRight: `1px solid ${tokens.colors.border}`,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: 8,
    paddingBottom: 8,
    justifyContent: 'space-between',
  },
  navGroup: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 2,
  },
  bottomGroup: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  navButton: {
    width: 36,
    height: 36,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: tokens.radius,
    color: tokens.colors.textMuted,
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    border: 'none',
    background: 'none',
    padding: 0,
  },
};
