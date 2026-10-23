/**
 * @file SiteHeader.tsx
 * @description The header on every page: the Mubazi mark and name, the household links on
 * wider screens, a bell for new messages (households), the language switcher and the theme
 * toggle. On phones the links move to the bottom bar; the bell stays here.
 */

import { Link, NavLink } from 'react-router-dom';
import Logo from '../Logo/Logo';
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
  /** Show the household links and the bell (not on the public pages). */
  links?: boolean;
}

/** Household links (wide screens) and the bell. Only rendered, and loaded, for households. */
function HouseholdBar() {
  const { t } = useI18n();
  const unread = unreadCount(useHouseholdFlags());
  return (
    <>
      <nav className={styles.nav} aria-label={t('nav.label')}>
        <ul className={styles.links}>
          {HOUSEHOLD_LINKS.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}>
                {t(item.label)}
                {item.to === '/messages' && unread > 0 && (
                  <>
                    <span className={styles.count} aria-hidden="true">
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
      <Link to="/messages" className={styles.bell} aria-label={unread > 0 ? t('nav.bellUnread', { count: unread }) : t('nav.bell')}>
        <Icon name="bell" size={20} />
        {unread > 0 && (
          <span className={styles.dot} aria-hidden="true">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </Link>
    </>
  );
}

function SiteHeader({ links = true }: SiteHeaderProps) {
  const { t } = useI18n();
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand} aria-label={t('brand.home')}>
          <Logo tagline={t('brand.tagline')} />
        </Link>

        <div className={styles.end}>
          {links && <HouseholdBar />}
          <LanguageSwitcher />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export default SiteHeader;
