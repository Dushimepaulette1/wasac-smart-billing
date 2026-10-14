/**
 * @file session.tsx
 * @description The household signed in on this phone: a 30-day session from
 * the one-time SMS code, kept in localStorage (a household's own phone, unlike
 * the staff session, which ends with the tab). A phone number can have several
 * accounts (a landlord's meters); one is chosen and used by every page.
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { setHouseholdToken } from '../api/client';
import type { HouseholdAccount, HouseholdSession } from '../api/types';

const SESSION_KEY = 'wasac.household';

interface Saved {
  token: string;
  expiresAt: number;
  phone: string;
  accounts: HouseholdAccount[];
  /** The chosen account; null until chosen when the phone has several. */
  customerId: string | null;
}

function load(): Saved | null {
  try {
    const raw = JSON.parse(window.localStorage.getItem(SESSION_KEY) ?? 'null') as Partial<Saved> | null;
    if (!raw || typeof raw.token !== 'string' || typeof raw.expiresAt !== 'number' || !Array.isArray(raw.accounts)) {
      return null;
    }
    if (raw.expiresAt * 1000 <= Date.now() || raw.accounts.length === 0) return null;
    return raw as Saved;
  } catch {
    return null;
  }
}

function save(saved: Saved | null): void {
  try {
    if (saved) window.localStorage.setItem(SESSION_KEY, JSON.stringify(saved));
    else window.localStorage.removeItem(SESSION_KEY);
  } catch {
    // Storage blocked: the session lasts until the page reloads.
  }
}

/** The chosen account, read outside React (shared loaders such as household/status.ts). */
let current: HouseholdAccount | null = null;

export function currentAccount(): HouseholdAccount | null {
  return current;
}

function chosen(saved: Saved | null): HouseholdAccount | null {
  if (!saved) return null;
  if (saved.accounts.length === 1) return saved.accounts[0] ?? null;
  return saved.accounts.find((a) => a.customer_id === saved.customerId) ?? null;
}

interface HouseholdValue {
  phone: string | null;
  accounts: HouseholdAccount[];
  /** The account in use; null when signed out, or before one is chosen. */
  account: HouseholdAccount | null;
  signedIn: boolean;
  start: (session: HouseholdSession) => void;
  choose: (customerId: string) => void;
  signOut: () => void;
}

const HouseholdContext = createContext<HouseholdValue | null>(null);

export function HouseholdProvider({ children }: { children: ReactNode }) {
  const [saved, setSaved] = useState<Saved | null>(() => {
    const s = load();
    setHouseholdToken(s?.token ?? null);
    current = chosen(s);
    return s;
  });

  const update = useCallback((next: Saved | null) => {
    save(next);
    current = chosen(next);
    setSaved(next);
  }, []);

  const signOut = useCallback(() => {
    setHouseholdToken(null);
    update(null);
  }, [update]);

  const start = useCallback(
    (session: HouseholdSession) => {
      setHouseholdToken(session.access_token, signOut);
      update({
        token: session.access_token,
        expiresAt: session.expires_at,
        phone: session.phone,
        accounts: session.accounts,
        customerId: session.accounts.length === 1 ? (session.accounts[0]?.customer_id ?? null) : null,
      });
    },
    [signOut, update],
  );

  const choose = useCallback(
    (customerId: string) => setSaved((s) => {
      if (!s) return s;
      const next = { ...s, customerId };
      save(next);
      current = chosen(next);
      return next;
    }),
    [],
  );

  // An expired or revoked token signs the household out on the next request.
  if (saved) setHouseholdToken(saved.token, signOut);

  const value = useMemo<HouseholdValue>(
    () => ({
      phone: saved?.phone ?? null,
      accounts: saved?.accounts ?? [],
      account: chosen(saved),
      signedIn: saved !== null,
      start,
      choose,
      signOut,
    }),
    [saved, start, choose, signOut],
  );
  return <HouseholdContext.Provider value={value}>{children}</HouseholdContext.Provider>;
}

export function useHousehold(): HouseholdValue {
  const ctx = useContext(HouseholdContext);
  if (!ctx) throw new Error('useHousehold must be used inside <HouseholdProvider>');
  return ctx;
}

/** The account every household page works with. Only for pages behind RequireHousehold. */
export function useAccount(): HouseholdAccount {
  const { account } = useHousehold();
  if (!account) throw new Error('useAccount needs a signed-in household (wrap the page in RequireHousehold)');
  return account;
}

/** Household pages: signed out goes to sign-in (then back); several accounts and none chosen goes to the chooser. */
export function RequireHousehold({ children }: { children: ReactNode }) {
  const { signedIn, account } = useHousehold();
  const location = useLocation();
  if (!signedIn || !account) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/sign-in?next=${next}`} replace />;
  }
  return <>{children}</>;
}
