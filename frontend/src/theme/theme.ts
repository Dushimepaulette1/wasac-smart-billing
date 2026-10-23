/**
 * @file theme.ts
 * @description Light and dark themes. The choice is remembered on the
 * device; until someone chooses, the phone or computer's own setting is
 * followed. index.html applies the stored theme before the first paint,
 * so a page never flashes the wrong one.
 */

import { useCallback, useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';
export const THEME_KEY = 'wasac.theme';

function stored(): Theme | null {
  try {
    const value = window.localStorage.getItem(THEME_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

function system(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

/** The page base colour per theme (tokens.css --stage-base). Phones colour the status bar
 * from theme-color and pick dark or light status icons to contrast with it. */
export const THEME_COLOR: Record<Theme, string> = { dark: '#040A16', light: '#EEF3F9' };

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  // Follow the theme the app shows, not the phone's system setting (index.html has one
  // theme-color per system scheme; both now carry the chosen one).
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.setAttribute('content', THEME_COLOR[theme]);
  });
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? currentTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Follow the system until the person chooses.
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: light)');
    if (!query) return undefined;
    const onChange = () => {
      if (!stored()) setTheme(system());
    };
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next: Theme = t === 'light' ? 'dark' : 'light';
      try {
        window.localStorage.setItem(THEME_KEY, next);
      } catch {
        // Storage blocked: the choice lasts for this page only.
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
