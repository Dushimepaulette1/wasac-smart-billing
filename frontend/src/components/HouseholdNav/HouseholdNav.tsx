/**
 * @file HouseholdNav.tsx
 * @description Bottom navigation for the household app on phones: Home, Bills, a raised
 * button to read the meter, Messages. The current page is marked by a filled pill, bold text
 * and aria-current, not by colour alone. Messages shows how many are new.
 */

import { NavLink } from 'react-router-dom';
import Icon, { type IconName } from '../Icon/Icon';
import { useI18n } from '../../i18n/I18nProvider';
import { unreadCount, useHouseholdFlags } from '../../household/status';
import styles from './HouseholdNav.module.css';

const ITEMS: Array<{ to: string; icon: IconName; label: string; main?: boolean }> = [
  { to: '/home', icon: 'home', label: 'nav.home' },
  { to: '/history', icon: 'bills', label: 'nav.bills' },
  { to: '/submit/camera', icon: 'camera', label: 'nav.read', main: true },
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
          <li key={item.to} className={item.main ? styles.mainItem : undefined}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                [styles.link, item.main ? styles.main : '', isActive ? styles.active : ''].filter(Boolean).join(' ')
              }
            >
              <span className={styles.iconWrap}>
                <Icon name={item.icon} size={item.main ? 26 : 22} />
                {item.to === '/messages' && unread > 0 && (
                  <span className={styles.badge} aria-hidden="true">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </span>
              <span className={styles.label}>{t(item.label)}</span>
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
