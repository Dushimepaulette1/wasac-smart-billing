/**
 * @file SiteHeader.tsx
 * @description The header on every page: the WASAC name in text (no logo
 * until approved assets exist), the household navigation on wider screens,
 * and the language switcher. On phones the navigation moves to the bottom.
 */

import { Link, NavLink } from 'react-router-dom';
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './SiteHeader.module.css';

export const HOUSEHOLD_LINKS = [
  { to: '/home', label: 'nav.home' },
  { to: '/history', label: 'nav.bills' },
  { to: '/messages', label: 'nav.messages' },
] as const;

interface SiteHeaderProps {
  /** Show the household links (not on the public landing page). */
  links?: boolean;
}

function SiteHeader({ links = true }: SiteHeaderProps) {
  const { t } = useI18n();
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand}>
          <span className={styles.wordmark}>WASAC</span>
          <span className={styles.tagline}>{t('brand.tagline')}</span>
        </Link>

        {links && (
          <nav className={styles.nav} aria-label={t('nav.label')}>
            <ul className={styles.links}>
              {HOUSEHOLD_LINKS.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
                  >
                    {t(item.label)}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        )}

        <div className={styles.end}>
          <LanguageSwitcher />
        </div>
      </div>
    </header>
  );
}

export default SiteHeader;
