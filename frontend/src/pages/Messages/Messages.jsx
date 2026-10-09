/**
 * @file Messages.jsx
 * @description What WASAC noticed about the household's readings, from
 * GET /api/anomaly/flags. Copy comes from the translation files by anomaly
 * type, never from the backend's English text. Leak alerts say what was
 * noticed, what to check, and what happens next.
 *
 * The API does not say whether a checked reading was accepted or rejected,
 * so a finished check is described neutrally.
 */

import React from 'react';
import Screen from '../../components/Screen/Screen';
import Icon from '../../components/Icon/Icon';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { api } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { HIGH_USE_TYPES } from '../../household/loadHome';
import { METER_ID } from '../../config';
import styles from './Messages.module.css';

/** Types a household gets a message for; NORMAL and BASELINE need none. */
export const SHOWN_TYPES = ['SPIKE', 'SUSTAINED_HIGH', 'MISREAD_SUSPECTED', 'METER_STUCK', 'UNUSUAL'];

function Message({ flag }) {
  const { t, date } = useI18n();
  const type = flag.anomaly_type;
  const open = flag.status === 'open';
  const when = date(flag.created_at);
  const leak = HIGH_USE_TYPES.includes(type);

  return (
    <article className={styles.message}>
      <h2 className="text-body">{t(`msg.${type}.title`)}</h2>

      <p>{t(`msg.${type}.noticed`, { date: when })}</p>

      {leak && (
        <>
          <p className={styles.checkTitle}>{t('msg.leak.checkTitle')}</p>
          <ul className={styles.checks}>
            <li>{t('msg.leak.check1')}</li>
            <li>{t('msg.leak.check2')}</li>
            <li>{t('msg.leak.check3')}</li>
          </ul>
          <p>{t('msg.leak.cost')}</p>
        </>
      )}

      {flag.requires_staff_review && (
        <p className={`${styles.status} ${open ? styles.checking : ''}`}>
          <Icon name={open ? 'clock' : 'check'} size={20} />
          <span>{open ? t('msg.status.open') : t('msg.status.resolved')}</span>
        </p>
      )}
    </article>
  );
}

function Messages() {
  const { t } = useI18n();
  const flags = useRequest(api.getHouseholdFlags, { immediate: true, args: [METER_ID] });
  const shown = flags.status === 'success' ? flags.data.filter((f) => SHOWN_TYPES.includes(f.anomaly_type)) : [];

  return (
    <Screen title={t('messages.title')} nav>
      {flags.status !== 'success' && (
        <RequestState status={flags.status} error={flags.error} onRetry={flags.retry} />
      )}

      {flags.status === 'success' && shown.length === 0 && <p className="measure">{t('messages.empty')}</p>}

      {shown.length > 0 && (
        <ul className={styles.list}>
          {shown.map((flag) => (
            <li key={flag.id}>
              <Message flag={flag} />
            </li>
          ))}
        </ul>
      )}
    </Screen>
  );
}

export default Messages;
