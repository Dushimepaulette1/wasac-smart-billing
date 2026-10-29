/**
 * @file LanguageSwitcher.tsx
 * @description Choose Kinyarwanda or English: a two-option pill switch ("Kiny | Eng"), one tap,
 * nothing to open. Each option carries the language's full name in itself for screen readers
 * and as a tooltip. The choice is remembered on the device by the I18nProvider.
 */

import { useI18n, LOCALES, LANGUAGE_NAMES, type Locale } from '../../i18n/I18nProvider';
import styles from './LanguageSwitcher.module.css';

const SHORT: Record<Locale, string> = { rw: 'Kiny', en: 'Eng' };

interface LanguageSwitcherProps {
  /** compact: in a header; full: with a visible label (account pages). */
  variant?: 'compact' | 'full';
}

function LanguageSwitcher({ variant = 'compact' }: LanguageSwitcherProps) {
  const { t, locale, setLocale } = useI18n();
  return (
    <div className={`${styles.root} ${styles[variant]}`}>
      {variant === 'full' && <span className={styles.label}>{t('language.label')}</span>}
      <div className={styles.switch} role="group" aria-label={t('language.label')}>
        {LOCALES.map((code) => (
          <button
            key={code}
            type="button"
            lang={code}
            className={`${styles.option} ${code === locale ? styles.current : ''}`}
            aria-pressed={code === locale}
            aria-label={LANGUAGE_NAMES[code]}
            title={LANGUAGE_NAMES[code]}
            onClick={() => setLocale(code)}
          >
            {SHORT[code]}
          </button>
        ))}
      </div>
    </div>
  );
}

export default LanguageSwitcher;
