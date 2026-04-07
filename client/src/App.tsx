import { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage } from './auth/LoginPage';
import { RegisterPage } from './auth/RegisterPage';
import { AppShell } from './components/layout/AppShell';
import { CommandPalette } from './components/CommandPalette';
import { InboxModule } from './domains/inbox/InboxModule';
import { TasksModule } from './domains/tasks/TasksModule';
import { JournalModule } from './domains/journal/JournalModule';
import { TemplatesModule } from './domains/templates/TemplatesModule';
import { SourcesModule } from './domains/sources/SourcesModule';
import { KBModule } from './domains/kb/KBModule';
import { MemoryModule } from './domains/memory/MemoryModule';
import { GoalsModule } from './domains/goals/GoalsModule';
import { TodayView } from './domains/today/TodayView';
import { PlaceholderModule } from './components/common/PlaceholderModule';
import type { NavModule } from './components/layout/Rail';

function AppContent() {
  const { user, loading, logout } = useAuth();
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [cmdKOpen, setCmdKOpen] = useState(false);

  // Global Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdKOpen((open) => !open);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  if (loading) {
    return null;
  }

  if (!user) {
    return authMode === 'login' ? (
      <LoginPage onSwitchToRegister={() => setAuthMode('register')} />
    ) : (
      <RegisterPage onSwitchToLogin={() => setAuthMode('login')} />
    );
  }

  return (
    <>
      <AppShell onLogout={logout}>
        {(activeModule: NavModule, onNavigate: (m: NavModule) => void) => {
          switch (activeModule) {
            case 'inbox':
              return <InboxModule />;
            case 'today':
              return <TodayView onNavigate={(m) => onNavigate(m as NavModule)} />;
            case 'tasks':
              return <TasksModule />;
            case 'journal':
              return <JournalModule />;
            case 'goals':
              return <GoalsModule />;
            case 'kb':
              return <KBModule />;
            case 'sources':
              return <SourcesModule />;
            case 'memory':
              return <MemoryModule />;
            case 'templates':
              return <TemplatesModule />;
            default:
              return <InboxModule />;
          }
        }}
      </AppShell>
      <CommandPalette
        open={cmdKOpen}
        onClose={() => setCmdKOpen(false)}
      />
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
