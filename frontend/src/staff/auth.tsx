/**
 * @file auth.tsx
 * @description Staff session: sign in, sign out, and the guard for staff
 * pages. The session lives in sessionStorage, so it ends when the browser
 * tab closes (safer on shared office computers) and is dropped as soon as
 * the backend rejects the token.
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { api, setStaffToken } from '../api/client';
import type { LoginResponse, StaffRole, StaffUser } from '../api/types';

const SESSION_KEY = 'wasac.staff';

interface Session {
  token: string;
  expiresAt: number;
  user: StaffUser;
}

function loadSession(): Session | null {
  try {
    const raw = JSON.parse(window.sessionStorage.getItem(SESSION_KEY) ?? 'null') as Partial<Session> | null;
    if (!raw || typeof raw.token !== 'string' || typeof raw.expiresAt !== 'number' || !raw.user) return null;
    if (raw.expiresAt * 1000 <= Date.now()) return null;
    return raw as Session;
  } catch {
    return null;
  }
}

function saveSession(session: Session | null): void {
  try {
    if (session) window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // Storage blocked: the session lasts until the page reloads.
  }
}

interface AuthValue {
  user: StaffUser | null;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => {
    const saved = loadSession();
    setStaffToken(saved?.token ?? null);
    return saved;
  });

  const signOut = useCallback(() => {
    setStaffToken(null);
    saveSession(null);
    setSession(null);
  }, []);

  const signIn = useCallback(
    async (username: string, password: string) => {
      const result: LoginResponse = await api.login(username, password);
      const next = { token: result.access_token, expiresAt: result.expires_at, user: result.user };
      setStaffToken(next.token, signOut);
      saveSession(next);
      setSession(next);
    },
    [signOut],
  );

  // An expired or revoked token signs the person out on the next request.
  if (session) setStaffToken(session.token, signOut);

  const value = useMemo(() => ({ user: session?.user ?? null, signIn, signOut }), [session, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}

const ROLE_ORDER: StaffRole[] = ['officer', 'supervisor', 'admin'];

/** officer < supervisor < admin; mirrors role_at_least in backend/app/api/routes/staff_auth.py. */
export function hasRole(user: StaffUser | null, role: StaffRole): boolean {
  if (!user) return false;
  return Math.max(0, ROLE_ORDER.indexOf(user.role as StaffRole)) >= ROLE_ORDER.indexOf(role);
}

/** Staff pages: send anyone not signed in to the sign-in page, then back.
 * With `role`, someone without it goes to the overview (the server refuses them anyway). */
export function RequireStaff({ children, role }: { children: ReactNode; role?: StaffRole }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/staff/sign-in?next=${next}`} replace />;
  }
  if (role && !hasRole(user, role)) return <Navigate to="/staff" replace />;
  return <>{children}</>;
}
