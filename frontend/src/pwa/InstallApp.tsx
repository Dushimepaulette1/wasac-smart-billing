/**
 * @file InstallApp.tsx
 * @description The "Install the app" button (Android) or hint (iPhone), shown
 * only when installing is possible and the app is not already installed.
 */

import Button from '../components/Button/Button';
import { useI18n } from '../i18n/I18nProvider';
import { useInstallPrompt } from './installPrompt';

function InstallApp({ className }: { className?: string }) {
  const { t } = useI18n();
  const { canInstall, showIosHint, install } = useInstallPrompt();
  if (canInstall) {
    return (
      <Button variant="secondary" icon="install" onClick={install} className={className}>
        {t('pwa.install')}
      </Button>
    );
  }
  if (showIosHint) {
    return <p className={`text-small ${className ?? ''}`}>{t('pwa.iosHint')}</p>;
  }
  return null;
}

export default InstallApp;
