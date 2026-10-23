/**
 * @file SiteHeader.tsx
 * @description The header on every page: the Mubazi name in text (no logo
 * until approved assets exist), the household navigation on wider screens,
 * and the language switcher. On phones the navigation moves to the bottom.
 */

import { Link, NavLink } from 'react-router-dom';
import Icon from '../Icon/Icon';
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher';
import ThemeToggle from '../ThemeToggle/ThemeToggle';
import { useI18n } from '../../i18n/I18nProvider';
import { unreadCount, useHouseholdFlags } from '../../household/status';
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

/** Household links; Messages shows how many are new. Only rendered (and loaded) for households. */
function HeaderLinks() {
  const { t } = useI18n();
  const unread = unreadCount(useHouseholdFlags());
  return (
    <nav className={styles.nav} aria-label={t('nav.label')}>
      <ul className={styles.links}>
        {HOUSEHOLD_LINKS.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
              {t(item.label)}
              {item.to === '/messages' && unread > 0 && (
                <>
                  <span className={styles.badge} aria-hidden="true">
                    {unread > 9 ? '9+' : unread}
                  </span>
                  <span className="visually-hidden">{t('nav.unread', { count: unread })}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** New messages at a glance, on every household page (phones included). */
function Bell() {
  const { t } = useI18n();
  const unread = unreadCount(useHouseholdFlags());
  return (
    <Link
      to="/messages"
      className={styles.bell}
      aria-label={unread > 0 ? t('nav.bellUnread', { count: unread }) : t('nav.bell')}
      title={t('nav.messages')}
    >
      <Icon name="bell" size={20} />
      {unread > 0 && (
        <span className={styles.bellCount} aria-hidden="true">
          {unread > 9 ? '9+' : unread}
        </span>
      )}
    </Link>
  );
}

function SiteHeader({ links = true }: SiteHeaderProps) {
  const { t } = useI18n();
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand}>
          <span className={styles.wordmark}>Mubazi</span>
          <span className={styles.tagline}>{t('brand.tagline')}</span>
        </Link>

        {links && <HeaderLinks />}

        <div className={styles.end}>
          {links && <Bell />}
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export default SiteHeader;
