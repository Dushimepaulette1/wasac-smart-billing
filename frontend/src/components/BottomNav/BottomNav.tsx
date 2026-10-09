/**
 * @file BottomNav.tsx
 * @description Fixed bottom navigation bar for mobile screens (≤ 768px).
 * Uses react-router-dom's useLocation to highlight the active route.
 * Features frosted glass styling and hand-crafted inline SVG icons.
 */

import type { ReactElement } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import styles from './BottomNav.module.css';

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
   SVG Icon Components — hand-crafted paths, no icon library
   -------------------------------------------------------------------------- */

/** Home icon */
function IconHome({ active }: NavIconProps) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
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

/** Camera / submit icon */
function IconCamera({ active }: NavIconProps) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <rect
        x="2"
        y="6"
        width="18"
        height="13"
        rx="2.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.10' : '0'}
      />
      <circle
        cx="11"
        cy="12.5"
        r="3.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
      />
      <path
        d="M8 6L9.5 3.5H12.5L14 6"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** History / clock icon */
function IconHistory({ active }: NavIconProps) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <circle
        cx="11"
        cy="11"
        r="8.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.08' : '0'}
      />
      <polyline
        points="11 6.5 11 11 14.5 13.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Account / person icon */
function IconAccount({ active }: NavIconProps) {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <circle
        cx="11"
        cy="8"
        r="3.5"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        fill={active ? 'currentColor' : 'none'}
        fillOpacity={active ? '0.12' : '0'}
      />
      <path
        d="M3.5 19C3.5 15.134 6.91 12 11 12C15.09 12 18.5 15.134 18.5 19"
        stroke="currentColor"
        strokeWidth={active ? '2' : '1.6'}
        strokeLinecap="round"
      />
    </svg>
  );
}

/* --------------------------------------------------------------------------
   Nav items configuration
   -------------------------------------------------------------------------- */
const NAV_ITEMS: NavItem[] = [
  {
    label: 'Home',
    href: '/home',
    matchPaths: ['/home'],
    Icon: IconHome,
  },
  {
    label: 'Submit',
    href: '/submit/camera',
    matchPaths: ['/submit'],
    Icon: IconCamera,
  },
  {
    label: 'History',
    href: '/history',
    matchPaths: ['/history'],
    Icon: IconHistory,
  },
  {
    label: 'Account',
    href: '/account',
    matchPaths: ['/account'],
    Icon: IconAccount,
  },
];

/**
 * BottomNav component — mobile-only fixed bottom navigation bar.
 */
function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (item: NavItem) =>
    item.matchPaths.some((path) => location.pathname.startsWith(path));

  return (
    <nav className={styles.nav} aria-label="Main navigation">
      {NAV_ITEMS.map((item) => {
        const active = isActive(item);
        return (
          <button
            key={item.href}
            type="button"
            className={[styles.item, active ? styles.itemActive : ''].filter(Boolean).join(' ')}
            onClick={() => navigate(item.href)}
            aria-current={active ? 'page' : undefined}
            aria-label={item.label}
          >
            <span className={styles.iconWrap}>
              <item.Icon active={active} />
              {active && <span className={styles.activeDot} aria-hidden="true" />}
            </span>
            <span className={[styles.label, active ? styles.labelVisible : ''].filter(Boolean).join(' ')}>
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

export default BottomNav;
