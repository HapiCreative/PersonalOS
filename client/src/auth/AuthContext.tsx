import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { setToken, clearToken } from '../api/client';
import { authApi } from '../api/endpoints';
import type { UserResponse } from '../types';

interface AuthContextValue {
  user: UserResponse | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check for existing token/user in localStorage
    const stored = localStorage.getItem('pos_user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        clearToken();
        localStorage.removeItem('pos_user');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await authApi.login(username, password);
    setToken(res.access_token);
    localStorage.setItem('pos_user', JSON.stringify(res.user));
    setUser(res.user);
  }, []);

  const register = useCallback(async (username: string, password: string, displayName?: string) => {
    const res = await authApi.register(username, password, displayName);
    setToken(res.access_token);
    localStorage.setItem('pos_user', JSON.stringify(res.user));
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    localStorage.removeItem('pos_user');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
