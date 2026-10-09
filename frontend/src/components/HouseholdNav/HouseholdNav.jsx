/**
 * @file HouseholdNav.jsx
 * @description Bottom navigation for the household app: Home, Bills,
 * Messages. The current page is marked by a bar, bold text and
 * aria-current, not by colour alone.
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import Icon from '../Icon/Icon';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './HouseholdNav.module.css';

const ITEMS = [
  { to: '/home', icon: 'home', label: 'nav.home' },
  { to: '/history', icon: 'bills', label: 'nav.bills' },
  { to: '/messages', icon: 'messages', label: 'nav.messages' },
];

function HouseholdNav() {
  const { t } = useI18n();
  return (
    <nav className={styles.nav} aria-label={t('nav.label')}>
      <ul className={styles.list}>
        {ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            >
              <Icon name={item.icon} />
              <span className="text-small">{t(item.label)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default HouseholdNav;
