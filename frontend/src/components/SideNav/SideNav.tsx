/**
 * @file SideNav.tsx
 * @description Left sidebar navigation for desktop screens (≥ 769px).
 * Shows WASAC branding at top and nav items with active route highlighting.
 * Reuses same SVG icon set as BottomNav.
 */

import type { ReactElement } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import styles from './SideNav.module.css';

interface NavIconProps {
  active: boolean;
}

interface NavItem {
  label: string;
  href: string;
  matchPaths: string[];
  Icon: (props: NavIconProps) => ReactElement;
}

/* --------------------------------------------------------------------------
   SVG Icon Components — identical paths to BottomNav for consistency
   -------------------------------------------------------------------------- */

function IconHome({ active }: NavIconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <path
        d="M2.5 9.5L11 2.5L19.5 9.5V19C19.5 19.552 19.052 20 18.5 20H14V15H8V20H3.5C2.948 20 2.5 19.552 2.5 19V9.5Z"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        strokeLinecap="round"
        strokeLinejoin="round"
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.12' : '0'}
      />
    </svg>
  );
}

function IconCamera({ active }: NavIconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <rect
        x="2" y="6" width="18" height="13" rx="2.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.10' : '0'}
      />
      <circle cx="11" cy="12.5" r="3.5" stroke="currentColor" strokeWidth={active ? '2' : '1.6'} />
      <path d="M8 6L9.5 3.5H12.5L14 6" stroke="currentColor" strokeWidth={active ? '2' : '1.6'} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconHistory({ active }: NavIconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <circle
        cx="11" cy="11" r="8.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.08' : '0'}
      />
      <polyline points="11 6.5 11 11 14.5 13.5" stroke="currentColor" strokeWidth={active ? '2' : '1.6'} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconAccount({ active }: NavIconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <circle
        cx="11" cy="8" r="3.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.12' : '0'}
      />
      <path d="M3.5 19C3.5 15.134 6.91 12 11 12C15.09 12 18.5 15.134 18.5 19" stroke="currentColor" strokeWidth={active ? '2' : '1.6'} strokeLinecap="round" />
    </svg>
  );
}

function IconOfficer({ active }: NavIconProps) {
  return (
    <svg width="20" height="20" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <rect
        x="3" y="3" width="16" height="16" rx="3"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.08' : '0'}
      />
      <line x1="7" y1="8" x2="15" y2="8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="7" y1="11" x2="13" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="7" y1="14" x2="11" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Nav items configuration
   -------------------------------------------------------------------------- */
const NAV_ITEMS: NavItem[] = [
  { label: 'Home', href: '/home', matchPaths: ['/home'], Icon: IconHome },
  { label: 'Submit Reading', href: '/submit/camera', matchPaths: ['/submit'], Icon: IconCamera },
  { label: 'Bill History', href: '/history', matchPaths: ['/history'], Icon: IconHistory },
  { label: 'My Account', href: '/account', matchPaths: ['/account'], Icon: IconAccount },
  { label: 'Officer Mode', href: '/officer', matchPaths: ['/officer'], Icon: IconOfficer },
];

/**
 * SideNav component — desktop left sidebar navigation.
 */
function SideNav() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (item: NavItem) =>
    item.matchPaths.some((path) => location.pathname.startsWith(path));

  return (
    <aside className={styles.sidebar} aria-label="Sidebar navigation">
      {/* WASAC brand header */}
      <div className={styles.brand}>
        <div className={styles.logoMark} aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="13" fill="var(--color-accent)" />
            <path
              d="M8 18C8 18 10 11 14 11C18 11 20 18 20 18"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx="14" cy="9" r="1.5" fill="white" />
          </svg>
        </div>
        <div className={styles.brandText}>
          <span className={styles.brandName}>WASAC</span>
          <span className={styles.brandTagline}>Smart Billing</span>
        </div>
      </div>

      {/* Divider */}
      <div className={styles.divider} aria-hidden="true" />

      {/* Navigation items */}
      <nav className={styles.nav} aria-label="Main navigation">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item);
          return (
            <button
              key={item.href}
              type="button"
              className={[styles.navItem, active ? styles.navItemActive : ''].filter(Boolean).join(' ')}
              onClick={() => navigate(item.href)}
              aria-current={active ? 'page' : undefined}
            >
              <span className={styles.navIcon}>
                <item.Icon active={active} />
              </span>
              <span className={styles.navLabel}>{item.label}</span>
              {active && <span className={styles.activeIndicator} aria-hidden="true" />}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

export default SideNav;
