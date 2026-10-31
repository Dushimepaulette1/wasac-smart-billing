/**
 * @file theme.ts
 * @description Light and dark themes. Light is the default on every device,
 * whatever the phone or computer is set to; a person's own choice is
 * remembered on the device. index.html applies it before the first paint,
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

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
}

/** The page base colour per theme (tokens.css --stage-base). Phones colour the status bar
 * from theme-color and pick dark or light status icons to contrast with it. */
export const THEME_COLOR: Record<Theme, string> = { dark: '#040A16', light: '#FFFFFF' };

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  // The status bar follows the theme the app shows, not the phone's system setting.
  document.querySelectorAll('meta[name="theme-color"]').forEach((meta) => {
    meta.setAttribute('content', THEME_COLOR[theme]);
  });
}

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? currentTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

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
