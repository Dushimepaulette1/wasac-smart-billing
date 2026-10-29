/**
 * @file Messages.tsx
 * @description What WASAC noticed about the household's readings, from
 * GET /api/anomaly/flags. Copy comes from the translation files by anomaly
 * type, never from the backend's English text. Leak alerts say what was
 * noticed, what to check, and what happens next.
 *
 * A checked reading says how the check ended: confirmed (the bill is ready)
 * or not confirmed (read the meter again). Opening Messages marks them read.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Icon from '../../components/Icon/Icon';
import Button from '../../components/Button/Button';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { api } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { HIGH_USE_TYPES } from '../../household/loadHome';
import { locationFinding } from '../../utils/location';
import { useAccount } from '../../household/session';
import { markMessagesSeen, refreshHouseholdFlags, shownMessages } from '../../household/status';
import type { AnomalyFlag } from '../../api/types';
import styles from './Messages.module.css';

export { SHOWN_TYPES } from '../../household/status';

/** How a check by a WASAC officer ended, from the flagged reading's status. */
function CheckStatus({ flag }: { flag: AnomalyFlag }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  if (flag.status === 'open') {
    return (
      <p className={`${styles.status} ${styles.checking}`}>
        <Icon name="clock" size={20} />
        <span>{t(flag.reading_status === 'pending_review' ? 'msg.status.open' : 'msg.status.followUp')}</span>
      </p>
    );
  }
  if (flag.reading_status === 'rejected') {
    return (
      <div className={styles.outcome}>
        <p className={styles.status}>
          <Icon name="alert" size={20} />
          <span>{t('msg.status.rejected')}</span>
        </p>
        <Button icon="camera" onClick={() => navigate('/submit/camera')}>
          {t('home.read')}
        </Button>
      </div>
    );
  }
  return (
    <p className={styles.status}>
      <Icon name="check" size={20} />
      <span>
        {flag.reading_status === 'valid' && flag.anomaly_type === 'NO_BASELINE' ? (
          t('msg.status.startingPoint')
        ) : flag.reading_status === 'valid' ? (
          <>
            {t('msg.status.accepted')} <Link to="/history">{t('msg.seeBills')}</Link>
          </>
        ) : (
          t('msg.status.resolved')
        )}
      </span>
    </p>
  );
}

const isDigitShift = (flag: AnomalyFlag) => flag.anomaly_type === 'MISREAD_SUSPECTED' && Boolean(flag.features?.digit_shift);

/** What was noticed; for a location check, which reason (camera photo far away, no location, gallery photo). */
function noticedKey(flag: AnomalyFlag): string {
  if (isDigitShift(flag)) return 'msg.MISREAD_SUSPECTED.digitShift';
  if (flag.anomaly_type !== 'LOCATION_CHECK') return `msg.${flag.anomaly_type}.noticed`;
  const reason = locationFinding(flag.features)?.reason ?? 'no_location';
  return `msg.LOCATION_CHECK.${reason}`;
}

function Message({ flag, onDelete }: { flag: AnomalyFlag; onDelete: (id: number) => void }) {
  const { t, date } = useI18n();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  // A reading still being checked keeps its message: its outcome is still to come.
  const canDelete = !(flag.status === 'open' && flag.reading_status === 'pending_review');
  const remove = async () => {
    setBusy(true);
    setFailed(false);
    try {
      await api.deleteMessage(flag.id);
      onDelete(flag.id);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };
  const type = flag.anomaly_type;
  const when = date(flag.created_at);
  const leak = HIGH_USE_TYPES.includes(type);

  return (
    <article className={`panel ${styles.message}`}>
      <h2 className="panel-title">{t(isDigitShift(flag) ? 'msg.MISREAD_SUSPECTED.digitShiftTitle' : `msg.${type}.title`)}</h2>

      <p>{t(noticedKey(flag), { date: when })}</p>

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

      {flag.requires_staff_review && <CheckStatus flag={flag} />}

      {canDelete && (
        <div className={styles.footer}>
          {failed && <span className="text-small">{t('messages.deleteFailed')}</span>}
          <Button variant="text" icon="trash" loading={busy} onClick={remove}>
            {t('messages.delete')}
          </Button>
        </div>
      )}
    </article>
  );
}

function Messages() {
  const account = useAccount();
  const meterId = account.meter_id ?? '';
  const { t } = useI18n();
  const flags = useRequest(api.getHouseholdFlags, { immediate: true, args: [meterId] });
  const [deleted, setDeleted] = useState<number[]>([]);
  const shown = flags.status === 'success' ? shownMessages(flags.data).filter((f) => !deleted.includes(f.id)) : [];
  const onDelete = (id: number) => {
    setDeleted((d) => [...d, id]);
    refreshHouseholdFlags(); // the bell and the bottom bar recount without it
  };

  // Everything on screen has now been seen on this device.
  useEffect(() => {
    if (flags.status === 'success') markMessagesSeen();
  }, [flags.status]);

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
              <Message flag={flag} onDelete={onDelete} />
            </li>
          ))}
        </ul>
      )}
    </Screen>
  );
}

export default Messages;
