/**
 * @file I18nProvider.tsx
 * @description Translation for Kinyarwanda, English and French without a
 * library. Strings live in ./locales/{rw,en,fr}.json as flat keys.
 *
 * Kinyarwanda and French strings are "TODO: translate" until reviewed by a
 * person (no machine translation). Until then those keys fall back to
 * English, so the app stays usable. `npm run i18n:sync` adds new English
 * keys to the other files.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import en from './locales/en.json';
import rw from './locales/rw.json';
import fr from './locales/fr.json';
import { makeFormatters, type Formatters } from './format';

export const TODO_MARK = 'TODO: translate';
export const LOCALES = ['rw', 'en', 'fr'] as const;
export type Locale = (typeof LOCALES)[number];

/** Values for {placeholders} in a string. */
export type TranslateVars = Record<string, string | number>;
export type Translate = (key: string, vars?: TranslateVars) => string;

/** Each language's own name; the same in every locale, so not translated. */
export const LANGUAGE_NAMES: Record<Locale, string> = { rw: 'Ikinyarwanda', en: 'English', fr: 'Français' };

const MESSAGES: Record<Locale, Record<string, string>> = { en, rw, fr };
const STORAGE_KEY = 'wasac.locale';

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value);
}

function initialLocale(): Locale {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (isLocale(saved)) return saved;
  } catch {
    // Storage blocked: fall through to the browser language.
  }
  const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
  return isLocale(browser) ? browser : 'en';
}

/**
 * Look up a key and fill {placeholders}. Falls back to English for keys
 * that are missing or not yet translated, and to the key itself if English
 * is missing too (so a gap is visible, not blank).
 */
export function translate(locale: Locale, key: string, vars?: TranslateVars): string {
  const own = MESSAGES[locale][key];
  const text = own && !own.startsWith(TODO_MARK) ? own : (en as Record<string, string>)[key] ?? key;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

export interface I18nValue extends Formatters {
  locale: Locale;
  setLocale: (next: string) => void;
  t: Translate;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children, locale: fixedLocale }: { children: ReactNode; locale?: Locale }) {
  const [locale, setLocaleState] = useState<Locale>(() => fixedLocale ?? initialLocale());

  const setLocale = useCallback((next: string) => {
    if (!isLocale(next)) return;
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

  const value = useMemo<I18nValue>(() => {
    const t: Translate = (key, vars) => translate(locale, key, vars);
    return { locale, setLocale, t, ...makeFormatters(locale, t) };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}
