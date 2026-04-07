import { useState, type FormEvent } from 'react';
import { useAuth } from './AuthContext';
import { tokens } from '../styles/tokens';

export function LoginPage({ onSwitchToRegister }: { onSwitchToRegister: () => void }) {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Personal OS</h1>
        <p style={styles.subtitle}>Sign in to continue</p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={styles.input}
            autoFocus
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        <p style={styles.switchText}>
          No account?{' '}
          <button onClick={onSwitchToRegister} style={styles.link}>
            Register
          </button>
        </p>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    background: tokens.colors.background,
  },
  card: {
    width: 360,
    padding: 32,
    background: tokens.colors.surface,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
  },
  title: {
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 24,
    color: tokens.colors.text,
    marginBottom: 4,
  },
  subtitle: {
    fontFamily: tokens.fonts.sans,
    color: tokens.colors.textMuted,
    fontSize: 14,
    marginBottom: 24,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  input: {
    width: '100%',
    padding: '10px 12px',
    background: tokens.colors.background,
    border: `1px solid ${tokens.colors.border}`,
    borderRadius: tokens.radius,
    color: tokens.colors.text,
    fontFamily: tokens.fonts.sans,
    fontSize: 14,
  },
  button: {
    width: '100%',
    padding: '10px 12px',
    background: tokens.colors.accent,
    color: tokens.colors.background,
    border: 'none',
    borderRadius: tokens.radius,
    fontFamily: tokens.fonts.sans,
    fontWeight: 600,
    fontSize: 14,
    cursor: 'pointer',
    marginTop: 4,
  },
  error: {
    color: tokens.colors.error,
    fontSize: 13,
    fontFamily: tokens.fonts.sans,
  },
  switchText: {
    marginTop: 16,
    textAlign: 'center' as const,
    color: tokens.colors.textMuted,
    fontSize: 13,
  },
  link: {
    color: tokens.colors.accent,
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontFamily: tokens.fonts.sans,
    fontSize: 13,
  },
};
