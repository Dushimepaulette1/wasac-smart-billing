/**
 * @file I18nProvider.jsx
 * @description Translation for Kinyarwanda, English and French without a
 * library. Strings live in ./locales/{rw,en,fr}.json as flat keys.
 *
 * Kinyarwanda and French strings are "TODO: translate" until reviewed by a
 * person (no machine translation). Until then those keys fall back to
 * English, so the app stays usable. `npm run i18n:sync` adds new English
 * keys to the other files.
 */

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import en from './locales/en.json';
import rw from './locales/rw.json';
import fr from './locales/fr.json';
import { makeFormatters } from './format';

export const TODO_MARK = 'TODO: translate';
export const LOCALES = ['rw', 'en', 'fr'];

/** Each language's own name; the same in every locale, so not translated. */
export const LANGUAGE_NAMES = { rw: 'Ikinyarwanda', en: 'English', fr: 'Français' };

const MESSAGES = { en, rw, fr };
const STORAGE_KEY = 'wasac.locale';

function initialLocale() {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (LOCALES.includes(saved)) return saved;
  } catch {
    // Storage blocked: fall through to the browser language.
  }
  const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
  return LOCALES.includes(browser) ? browser : 'en';
}

/**
 * Look up a key and fill {placeholders}. Falls back to English for keys
 * that are missing or not yet translated, and to the key itself if English
 * is missing too (so a gap is visible, not blank).
 */
export function translate(locale, key, vars) {
  const own = MESSAGES[locale]?.[key];
  const text = own && !own.startsWith(TODO_MARK) ? own : en[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name) => (name in vars ? String(vars[name]) : match));
}

const I18nContext = createContext(null);

export function I18nProvider({ children, locale: fixedLocale }) {
  const [locale, setLocaleState] = useState(() => fixedLocale || initialLocale());

  const setLocale = useCallback((next) => {
    if (!LOCALES.includes(next)) return;
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not saved; the choice still applies for this visit.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo(() => {
    const t = (key, vars) => translate(locale, key, vars);
    return { locale, setLocale, t, ...makeFormatters(locale, t) };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/**
 * @returns {{
 *   locale: string, setLocale: (l: string) => void,
 *   t: (key: string, vars?: object) => string,
 *   rwf: (amount: number) => string,
 *   volume: (m3: number) => string,
 *   date: (iso: string) => string,
 *   monthYear: (iso: string) => string,
 *   month: (iso: string) => string,
 * }}
 */
export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
