/**
 * Section 9.1: App Shell layout.
 * Rail (48px) + List Pane (240px, resizable) + Detail Pane.
 * Today View uses full width (no list/detail split).
 */

import { useState, type ReactNode } from 'react';
import { Rail, type NavModule } from './Rail';
import { tokens } from '../../styles/tokens';

interface AppShellProps {
  onLogout: () => void;
  children: (activeModule: NavModule, onNavigate: (m: NavModule) => void) => ReactNode;
}

export function AppShell({ onLogout, children }: AppShellProps) {
  const [activeModule, setActiveModule] = useState<NavModule>('inbox');

  return (
    <div style={styles.shell}>
      <Rail active={activeModule} onNavigate={setActiveModule} onLogout={onLogout} />
      <div style={styles.main}>
        {children(activeModule, setActiveModule)}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: {
    display: 'flex',
    height: '100%',
    width: '100%',
    overflow: 'hidden',
  },
  main: {
    flex: 1,
    display: 'flex',
    height: '100%',
    overflow: 'hidden',
  },
};
