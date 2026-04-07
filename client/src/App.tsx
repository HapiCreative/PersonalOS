import { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { LoginPage } from './auth/LoginPage';
import { RegisterPage } from './auth/RegisterPage';
import { AppShell } from './components/layout/AppShell';
import { CommandPalette } from './components/CommandPalette';
import { InboxModule } from './domains/inbox/InboxModule';
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
        {(activeModule: NavModule) => {
          switch (activeModule) {
            case 'inbox':
              return <InboxModule />;
            case 'today':
              return <PlaceholderModule name="Today" phase="Phase 4" />;
            case 'tasks':
              return <PlaceholderModule name="Tasks" phase="Phase 2" />;
            case 'journal':
              return <PlaceholderModule name="Journal" phase="Phase 2" />;
            case 'goals':
              return <PlaceholderModule name="Goals" phase="Phase 4" />;
            case 'kb':
              return <PlaceholderModule name="Knowledge Base" phase="Phase 3" />;
            case 'sources':
              return <PlaceholderModule name="Sources" phase="Phase 3" />;
            case 'memory':
              return <PlaceholderModule name="Memory" phase="Phase 3" />;
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
