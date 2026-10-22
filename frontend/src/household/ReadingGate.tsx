/**
 * @file ReadingGate.tsx
 * @description In front of the camera and confirm pages: a household may send
 * one reading per billing period, one at a time (backend
 * app/services/reading_window.py). If a reading is waiting for an officer, or
 * this period's reading is already in, say so instead of opening the camera.
 * If the check itself fails (no connection), let the household carry on: the
 * backend refuses the reading anyway, and the confirm page explains.
 */

import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import Screen from '../components/Screen/Screen';
import Button from '../components/Button/Button';
import Progress from '../components/Progress/Progress';
import { api } from '../api/client';
import useRequest from '../api/useRequest';
import { useI18n } from '../i18n/I18nProvider';
import { useAccount } from './session';

function ReadingGate({ children }: { children: ReactNode }) {
  const { t, date } = useI18n();
  const navigate = useNavigate();
  const account = useAccount();
  const customer = useRequest(api.getCustomer, { immediate: true, args: [account.customer_id] });

  if (customer.status === 'failed') return <>{children}</>;
  if (customer.status !== 'success') {
    return (
      <Screen title={t('home.read')}>
        <Progress label={t('status.loading')} />
      </Screen>
    );
  }

  const { reading_pending: pending, next_reading_from: opensOn } = customer.data;
  if (!pending && !opensOn) return <>{children}</>;

  return (
    <Screen
      title={pending ? t('home.checkingTitle') : t('home.readingInTitle')}
      lede={<p>{pending ? t('gate.pendingBody') : t('home.readingInBody', { date: date(opensOn) })}</p>}
      back="/home"
      action={
        <Button fullWidth onClick={() => navigate(pending ? '/messages' : '/home')}>
          {pending ? t('gate.seeMessages') : t('gate.backHome')}
        </Button>
      }
    >
      {null}
    </Screen>
  );
}

export default ReadingGate;
