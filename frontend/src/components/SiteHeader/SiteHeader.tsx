/**
 * @file SiteHeader.tsx
 * @description The header on every page: the Mubazi mark and name (no logo
 * until approved assets exist), the household navigation on wider screens,
 * and the language switcher. On phones the navigation moves to the bottom.
 */

import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import Icon from '../Icon/Icon';
import { LogoMark } from '../Logo/Logo';
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher';
import ThemeToggle from '../ThemeToggle/ThemeToggle';
import { useI18n } from '../../i18n/I18nProvider';
import { unreadCount, useHouseholdFlags } from '../../household/status';
import { useHousehold } from '../../household/session';
import { formatRwandanPhone } from '../../utils/phone';
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

/** The household's account: which number is signed in, switch meter, sign out. */
function AccountMenu() {
  const { t } = useI18n();
  const household = useHousehold();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on Escape or a click outside.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onClick);
    };
  }, [open]);

  if (!household.signedIn) return null;
  const signOut = () => {
    setOpen(false);
    household.signOut();
    navigate('/sign-in', { replace: true });
  };
  return (
    <div className={styles.account} ref={ref}>
      <button
        type="button"
        className={styles.bell}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('header.account')}
        title={t('header.account')}
        onClick={() => setOpen((o) => !o)}
      >
        <Icon name="user" size={20} />
      </button>
      {open && (
        <div className={styles.menu} role="menu">
          <p className={styles.menuWho}>
            <span className="text-small text-secondary">{t('header.signedInWith')}</span>
            <span className="num">{formatRwandanPhone(household.phone)}</span>
          </p>
          {household.accounts.length > 1 && (
            <button type="button" role="menuitem" className={styles.menuItem}
              onClick={() => { setOpen(false); navigate('/sign-in?switch=1'); }}>
              <Icon name="households" size={18} />
              {t('home.switchMeter')}
            </button>
          )}
          <button type="button" role="menuitem" className={styles.menuItem} onClick={signOut}>
            <Icon name="logout" size={18} />
            {t('home.signOut')}
          </button>
        </div>
      )}
    </div>
  );
}

function SiteHeader({ links = true }: SiteHeaderProps) {
  const { t } = useI18n();
  const onSignIn = /sign-in/.test(useLocation().pathname);
  return (
    <header className={`${styles.header} ${links ? styles.household : ''}`}>
      <div className={styles.inner}>
        <Link to="/" className={styles.brand}>
          <LogoMark />
          <span className={styles.wordmark}>Mubazi</span>
        </Link>

        {links && <HeaderLinks />}

        <div className={styles.end}>
          {links && <Bell />}
          <LanguageSwitcher />
          <ThemeToggle />
          {links && <AccountMenu />}
          {/* The one call to action: sign in (public pages) or read the meter (households).
              Not on the sign-in pages themselves. */}
          {!onSignIn && (
            <Link to={links ? '/submit/camera' : '/home'} className={styles.cta}>
              {links ? t('header.read') : t('header.signIn')}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

export default SiteHeader;
