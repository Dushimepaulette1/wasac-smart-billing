/**
 * @file NotFound.tsx
 * @description An address that does not exist: say so, and offer the way back.
 */

import { useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import { useI18n } from '../../i18n/I18nProvider';

export default function NotFound() {
  const navigate = useNavigate();
  const { t } = useI18n();
  return (
    <Screen
      title={t('notFound.title')}
      lede={<p>{t('notFound.body')}</p>}
      action={
        <>
          <Button variant="secondary" onClick={() => navigate(-1)}>
            {t('action.back')}
          </Button>
          <Button onClick={() => navigate('/')}>{t('notFound.home')}</Button>
        </>
      }
    >
      {null}
    </Screen>
  );
}
