/**
 * @file LanguageSwitcher.tsx
 * @description Choose Ikinyarwanda, English or Français. Each language is
 * named in itself, so anyone can find theirs. The choice is remembered on
 * the device by the I18nProvider.
 */

import { useId } from 'react';
import { useI18n, LOCALES, LANGUAGE_NAMES } from '../../i18n/I18nProvider';
import styles from './LanguageSwitcher.module.css';

interface LanguageSwitcherProps {
  /** compact: header pill with a hidden label; full: labelled field. */
  variant?: 'compact' | 'full';
}

function LanguageSwitcher({ variant = 'compact' }: LanguageSwitcherProps) {
  const { t, locale, setLocale } = useI18n();
  const id = useId();
  return (
    <div className={`${styles.root} ${styles[variant]}`}>
      <label htmlFor={id} className={variant === 'compact' ? 'visually-hidden' : styles.label}>
        {t('language.label')}
      </label>
      <select id={id} value={locale} onChange={(e) => setLocale(e.target.value)} className={styles.select}>
        {LOCALES.map((code) => (
          <option key={code} value={code} lang={code}>
            {LANGUAGE_NAMES[code]}
          </option>
        ))}
      </select>
    </div>
  );
}

export default LanguageSwitcher;
