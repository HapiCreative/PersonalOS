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
import { ProjectsModule } from './domains/projects/ProjectsModule';
import { TodayView } from './domains/today/TodayView';
import { ReviewModule } from './domains/review/ReviewModule';
import { CleanupModule } from './domains/cleanup/CleanupModule';
import { AIModule } from './domains/ai/AIModule';
import { PlaceholderModule } from './components/common/PlaceholderModule';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { SettingsModule } from './domains/settings/SettingsModule';
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
          // Phase 10: ErrorBoundary wraps each module for graceful error handling
          const content = (() => { switch (activeModule) {
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
            case 'projects':
              return <ProjectsModule />;
            case 'kb':
              return <KBModule />;
            case 'sources':
              return <SourcesModule />;
            case 'memory':
              return <MemoryModule />;
            case 'review':
              return <ReviewModule />;
            case 'ai':
              return <AIModule />;
            case 'cleanup':
              return <CleanupModule onNavigate={(m) => onNavigate(m as NavModule)} />;
            case 'templates':
              return <TemplatesModule />;
            case 'settings':
              return <SettingsModule />;
            default:
              return <InboxModule />;
          }})();
          return <ErrorBoundary key={activeModule}>{content}</ErrorBoundary>;
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
