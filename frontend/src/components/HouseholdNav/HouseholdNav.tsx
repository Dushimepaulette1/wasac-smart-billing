/**
 * @file HouseholdNav.tsx
 * @description Bottom navigation for the household app: Home, Bills,
 * Messages. The current page is marked by a bar, bold text and
 * aria-current, not by colour alone. Messages shows how many are new.
 */

import { NavLink } from 'react-router-dom';
import Icon, { type IconName } from '../Icon/Icon';
import { useI18n } from '../../i18n/I18nProvider';
import { unreadCount, useHouseholdFlags } from '../../household/status';
import styles from './HouseholdNav.module.css';

const ITEMS: Array<{ to: string; icon: IconName; label: string }> = [
  { to: '/home', icon: 'home', label: 'nav.home' },
  { to: '/history', icon: 'bills', label: 'nav.bills' },
  { to: '/messages', icon: 'messages', label: 'nav.messages' },
];

function HouseholdNav() {
  const { t } = useI18n();
  const flags = useHouseholdFlags();
  const unread = unreadCount(flags);
  return (
    <nav className={styles.nav} aria-label={t('nav.label')}>
      <ul className={styles.list}>
        {ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
            >
              <span className={styles.iconWrap}>
                <Icon name={item.icon} />
                {item.to === '/messages' && unread > 0 && (
                  <span className={styles.badge} aria-hidden="true">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </span>
              <span className="text-small">{t(item.label)}</span>
              {item.to === '/messages' && unread > 0 && (
                <span className="visually-hidden">{t('nav.unread', { count: unread })}</span>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default HouseholdNav;
