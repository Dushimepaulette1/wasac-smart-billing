/**
 * @file CustomerHome.tsx
 * @description Home leads with the household's next action, in words:
 * pay the bill that is due, or read the meter. No big-number hero and no
 * counter here; the counter belongs to readings.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import loadHome from '../../household/loadHome';
import { useAccount, useHousehold } from '../../household/session';
import { formatRwandanPhone } from '../../utils/phone';
import InstallApp from '../../pwa/InstallApp';
import PushOptIn from '../../pwa/PushOptIn';
import type { AnomalyFlag } from '../../api/types';
import styles from './CustomerHome.module.css';
import { amountOwed } from '../../utils/bill';

const SEEN_KEY = 'mubazi.decisionSeen';

function seenDecisions(meterId: string): number[] {
  try {
    return JSON.parse(window.localStorage.getItem(`${SEEN_KEY}:${meterId}`) ?? '[]') as number[];
  } catch {
    return [];
  }
}

/** "Your reading was accepted / please read again", until the household closes it. */
function DecisionBanner({ flag, meterId }: { flag: AnomalyFlag; meterId: string }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [hidden, setHidden] = useState(() => seenDecisions(meterId).includes(flag.id));
  if (hidden) return null;
  const close = () => {
    try {
      window.localStorage.setItem(`${SEEN_KEY}:${meterId}`, JSON.stringify([...seenDecisions(meterId), flag.id].slice(-20)));
    } catch {
      // Storage blocked: it closes for now and may show again next time.
    }
    setHidden(true);
  };
  const accepted = flag.reading_status === 'valid';
  return (
    <Notice
      tone={accepted ? 'done' : 'held'}
      live
      title={t(accepted ? 'home.decision.acceptedTitle' : 'home.decision.rejectedTitle')}
      actions={
        <>
          {accepted ? (
            <Button variant="secondary" onClick={() => navigate('/history')}>
              {t('home.decision.seeBills')}
            </Button>
          ) : (
            <Button icon="camera" onClick={() => navigate('/submit/camera')}>
              {t('home.read')}
            </Button>
          )}
          <Button variant="text" onClick={close}>
            {t('action.dismiss')}
          </Button>
        </>
      }
    >
      {t(accepted ? 'home.decision.acceptedBody' : 'home.decision.rejectedBody')}
    </Notice>
  );
}

function CustomerHome() {
  const account = useAccount();
  const household = useHousehold();
  const customerId = account.customer_id;
  const meterId = account.meter_id ?? '';
  const { t, rwf, date, month } = useI18n();
  const navigate = useNavigate();
  const home = useRequest(loadHome, { immediate: true, args: [customerId, meterId] });

  if (home.status !== 'success') {
    return (
      <Screen title={t('app.name')} nav>
        <RequestState status={home.status} error={home.error} onRetry={home.retry} />
      </Screen>
    );
  }

  const { customer, newestBill, highUse, decision } = home.data;
  const checking = home.data.checking || customer.reading_pending;
  // This period's reading is in: the next one opens on this date.
  const opensOn = customer.next_reading_from;
  const due = newestBill && newestBill.payment_status !== 'paid' ? newestBill : null;
  const readMeter = () => navigate('/submit/camera');

  // While a reading waits for an officer, or this period's reading is in, a new one is not asked for.
  const readButton = checking || opensOn ? null : (
    // Phones have the Read button in the bottom bar; this one is for wide screens.
    <Button variant={due ? 'text' : undefined} fullWidth={!due} icon="camera" onClick={readMeter} className={styles.readAction}>
      {t('home.read')}
    </Button>
  );
  // The bill due has its own card (with the pay button); the pinned action is for reading.
  const action = readButton;

  let title = t('home.readPrompt');
  if (due) title = t('home.billDue', { month: month(due.created_at), amount: rwf(amountOwed(due)) });
  else if (checking) title = t('home.checkingTitle');
  else if (opensOn) title = t('home.readingInTitle');

  return (
    <Screen
      step={customer.name}
      title={title}
      lede={
        due ? null : checking ? (
          <p>{t('home.checkingBody')}</p>
        ) : opensOn ? (
          <p>{t('home.readingInBody', { date: date(opensOn) })}</p>
        ) : null
      }
      nav
      action={action}
    >
      {decision && <DecisionBanner flag={decision} meterId={meterId} />}

      {(customer.credit_available ?? 0) >= 1 && (
        <p className="text-small">{t('home.credit', { amount: rwf(customer.credit_available ?? 0) })}</p>
      )}

      {due && (
        <section className={`panel panel-ink ${styles.billCard}`} aria-labelledby="due-title">
          <p id="due-title" className={styles.billLabel}>
            {t('home.billFor', { month: month(due.created_at) })}
          </p>
          <p className={styles.billAmount}>{rwf(amountOwed(due))}</p>
          <div className={styles.billActions}>
            <Button onClick={() => navigate(`/payment?bill=${due.bill_id}`)}>
              {t('pay.action', { amount: rwf(amountOwed(due)) })}
            </Button>
            <Button variant="text" onClick={() => navigate(`/bill?id=${due.bill_id}`)}>
              {t('home.seeBill')}
            </Button>
          </div>
        </section>
      )}

      {((checking && due) || highUse) && (
        <div className={styles.notices}>
          {checking && due && (
            <Notice tone="held" title={t('home.checkingTitle')}>
              {t('home.checkingBody')}
            </Notice>
          )}

          {highUse && (
            <Notice
              tone="error"
              actions={
                <Button variant="text" onClick={() => navigate('/messages')}>
                  {t('home.readMessage')}
                </Button>
              }
            >
              {t('home.highUse')}
            </Notice>
          )}
        </div>
      )}

      {/* One strip: three facts side by side on wide screens, stacked on phones. */}
      <section className={`panel ${styles.meterPanel}`} aria-labelledby="meter-title">
        <h2 id="meter-title" className="panel-title">
          {t('home.meterTitle')}
        </h2>
        <dl className={styles.facts}>
          <div className={styles.fact}>
            <dt>{t('home.meter')}</dt>
            <dd className="code">{customer.meter_id}</dd>
          </div>
          <div className={styles.fact}>
            <dt>{t('home.lastReading')}</dt>
            <dd className="num">
              {formatReading(cellsFromCubicMetres(customer.last_reading))} {t('counter.cubicMetres')}
            </dd>
          </div>
          {customer.last_reading_date && (
            <div className={styles.fact}>
              <dt>{t('home.lastReadOn')}</dt>
              <dd className="num">{date(customer.last_reading_date)}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className={`panel ${styles.signedIn}`} aria-label={t('home.signedInTitle')}>
        <p className="text-small">
          {t('home.signedInAs', { phone: formatRwandanPhone(household.phone) })}
        </p>
        <PushOptIn />
        <div className={styles.signedInActions}>
          <InstallApp />
          {household.accounts.length > 1 && (
            <Button variant="text" onClick={() => navigate('/sign-in?switch=1')}>
              {t('home.switchMeter')}
            </Button>
          )}
          <Button variant="text" onClick={household.signOut}>
            {t('home.signOut')}
          </Button>
        </div>
      </section>
    </Screen>
  );
}

export default CustomerHome;
