/**
 * @file StaffLayout.tsx
 * @description The staff dashboard frame: a sidebar (Overview, Review
 * queue, Households, Activity, Staff accounts for admins, the signed-in
 * person with My account, sign out) and a top bar (menu
 * button, page title, language, theme).
 *
 * Wide screens (1024px+): the sidebar is always there and can be collapsed
 * to icons with the menu button; the choice is remembered.
 * Narrower screens: the sidebar is hidden and the menu button opens it over
 * the page; it closes with Escape, a tap outside, or after choosing a page.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import Icon, { type IconName } from '../Icon/Icon';
import { LogoMark } from '../Logo/Logo';
import LanguageSwitcher from '../LanguageSwitcher/LanguageSwitcher';
import ThemeToggle from '../ThemeToggle/ThemeToggle';
import { useI18n } from '../../i18n/I18nProvider';
import { hasRole, useAuth } from '../../staff/auth';
import type { StaffRole } from '../../api/types';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import styles from './StaffLayout.module.css';

const COLLAPSED_KEY = 'wasac.sidebarCollapsed';
const WIDE = '(min-width: 1024px)';

interface NavItem {
  to: string;
  icon: IconName;
  label: string;
  end?: boolean;
  /** Shown only to this role and higher ones. */
  role?: StaffRole;
}

const NAV: NavItem[] = [
  { to: '/staff', icon: 'overview', label: 'staff.nav.overview', end: true },
  { to: '/staff/review', icon: 'queue', label: 'staff.nav.review' },
  { to: '/staff/households', icon: 'households', label: 'staff.nav.households' },
  { to: '/staff/payments', icon: 'wallet', label: 'staff.nav.payments' },
  { to: '/staff/corrections', icon: 'gauge', label: 'staff.nav.corrections', role: 'supervisor' },
  { to: '/staff/activity', icon: 'activity', label: 'staff.nav.activity' },
  { to: '/staff/accounts', icon: 'user', label: 'staff.nav.accounts', role: 'admin' },
  { to: '/staff/sms', icon: 'messages', label: 'staff.nav.sms', role: 'admin' },
];

function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia?.(query).matches ?? true);
  useEffect(() => {
    const list = window.matchMedia?.(query);
    if (!list) return undefined;
    const onChange = () => setMatches(list.matches);
    list.addEventListener('change', onChange);
    return () => list.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

interface StaffLayoutProps {
  title: string;
  /** Short line under the title. */
  lede?: ReactNode;
  /** Count shown beside "Review queue" in the sidebar. */
  reviewCount?: number;
  children: ReactNode;
}

function StaffLayout({ title, lede, reviewCount, children }: StaffLayoutProps) {
  const { t } = useI18n();
  const { user, signOut } = useAuth();
  const wide = useMedia(WIDE);
  // Pages that already load the queue pass their count; others load it here.
  const queueCount = useRequest(
    () => api.reviewQueue().then((q) => q.length),
    reviewCount === undefined ? { immediate: true, args: [] } : {},
  );
  const waiting = reviewCount ?? (queueCount.status === 'success' ? queueCount.data : undefined);
  const approvals = useRequest(
    () => Promise.all([api.meterCorrections('awaiting_approval'), api.billCorrections('awaiting_approval')])
      .then(([meters, bills]) => meters.length + bills.length),
    hasRole(user, 'supervisor') ? { immediate: true, args: [] } : {},
  );
  const counts: Partial<Record<IconName, number>> = {
    queue: waiting,
    gauge: approvals.status === 'success' ? approvals.data : undefined,
  };
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(COLLAPSED_KEY) === '1';
    } catch {
      return false;
    }
  });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    document.title = `${title} | ${t('staff.appName')}`;
    headingRef.current?.focus({ preventScroll: true });
  }, [title, t]);

  // Choosing a page closes the drawer.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  // Drawer: Escape closes it and focus returns to the menu button.
  useEffect(() => {
    if (!drawerOpen) return undefined;
    firstLinkRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDrawerOpen(false);
        menuButtonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [drawerOpen]);

  const toggleMenu = () => {
    if (wide) {
      setCollapsed((c) => {
        try {
          window.localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1');
        } catch {
          // Storage blocked: the choice lasts for this page only.
        }
        return !c;
      });
    } else {
      setDrawerOpen((o) => !o);
    }
  };

  const isCollapsed = wide && collapsed;
  const expanded = wide ? !collapsed : drawerOpen;
  const shellClass = [styles.shell, 'stage', 'staff', isCollapsed ? styles.collapsed : '', drawerOpen ? styles.drawerOpen : '']
    .filter(Boolean)
    .join(' ');

  return (
    <div className={shellClass}>
      <a href="#staff-main" className={styles.skip}>
        {t('staff.skip')}
      </a>

      {drawerOpen && <button type="button" className={styles.scrim} aria-label={t('staff.closeMenu')} onClick={() => setDrawerOpen(false)} tabIndex={-1} />}

      <aside id="staff-sidebar" className={styles.sidebar} aria-label={t('staff.sidebar')} {...(!wide && !drawerOpen ? { hidden: true } : {})}>
        <div className={styles.brand}>
          <span className={`${styles.brandRow} on-ink`}>
            <LogoMark size={isCollapsed ? 32 : 34} />
            {!isCollapsed && <span className={styles.wordmark}>Mubazi</span>}
          </span>
          {!isCollapsed && <span className={styles.brandSub}>{t('staff.appName')}</span>}
        </div>

        <nav className={styles.nav} aria-label={t('staff.sidebar')}>
          <ul>
            {NAV.filter((item) => !item.role || hasRole(user, item.role)).map((item, i) => (
              <li key={item.to}>
                <NavLink
                  ref={i === 0 ? firstLinkRef : undefined}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
                  title={isCollapsed ? t(item.label) : undefined}
                >
                  <Icon name={item.icon} size={22} />
                  <span className={isCollapsed ? 'visually-hidden' : styles.linkLabel}>{t(item.label)}</span>
                  {(counts[item.icon] ?? 0) > 0 && (
                    <span className={styles.count}>
                      {counts[item.icon]}
                      <span className="visually-hidden"> {t('staff.waiting')}</span>
                    </span>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className={styles.account}>
          {user && !isCollapsed && (
            <div className={styles.person}>
              <span className={styles.avatar} aria-hidden="true">
                {user.full_name.charAt(0)}
              </span>
              <span className={styles.personText}>
                <span className={styles.personName}>{user.full_name}</span>
                <span className="text-small">{t(`staff.role.${user.role}`)}</span>
              </span>
            </div>
          )}
          <NavLink
            to="/staff/account"
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            title={isCollapsed ? t('staff.nav.account') : undefined}
          >
            <Icon name="lock" size={22} />
            <span className={isCollapsed ? 'visually-hidden' : styles.linkLabel}>{t('staff.nav.account')}</span>
          </NavLink>
          <button type="button" className={styles.link} onClick={signOut} title={isCollapsed ? t('staff.signOut') : undefined}>
            <Icon name="logout" size={22} />
            <span className={isCollapsed ? 'visually-hidden' : styles.linkLabel}>{t('staff.signOut')}</span>
          </button>
        </div>
      </aside>

      <div className={styles.content}>
        <header className={styles.topbar}>
          <button
            ref={menuButtonRef}
            type="button"
            className={styles.menuButton}
            onClick={toggleMenu}
            aria-controls="staff-sidebar"
            aria-expanded={expanded}
            aria-label={wide ? (collapsed ? t('staff.expandMenu') : t('staff.collapseMenu')) : t('staff.openMenu')}
          >
            <Icon name={wide ? 'sidebar' : 'menu'} size={22} />
          </button>
          <div className={styles.topbarEnd}>
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        <main id="staff-main" className={styles.main}>
          <div className={styles.head}>
            <h1 ref={headingRef} tabIndex={-1} className={`${styles.title} page-title`}>
              {title}
            </h1>
            {lede && <div className={styles.lede}>{lede}</div>}
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}

export default StaffLayout;
