/**
 * @file ThemeToggle.tsx
 * @description Switch between light and dark. The button names what it
 * will do ("Switch to light mode"), and shows the matching icon.
 */

import Icon from '../Icon/Icon';
import { useTheme } from '../../theme/theme';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './ThemeToggle.module.css';

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const { t } = useI18n();
  const label = theme === 'light' ? t('theme.toDark') : t('theme.toLight');
  return (
    <button type="button" className={styles.toggle} onClick={toggle} aria-label={label} title={label}>
      {/* key: the icon pops in again each time the theme changes. */}
      <Icon key={theme} name={theme === 'light' ? 'moon' : 'sun'} size={20} />
    </button>
  );
}

export default ThemeToggle;
