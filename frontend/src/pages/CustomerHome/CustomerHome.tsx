/**
 * @file CustomerHome.tsx
 * @description Home: a greeting, then one status card that says what to do now (pay the bill
 * that is due, wait while a reading is checked, wait for the next reading period, or read the
 * meter), a banner when an officer has decided a reading, quick actions, the last months' use
 * as a chart, the meter, and the account.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Icon, { type IconName } from '../../components/Icon/Icon';
import Notice from '../../components/Notice/Notice';
import RequestState from '../../components/RequestState/RequestState';
import UsageChart from '../../components/UsageChart/UsageChart';
import useRequest from '../../api/useRequest';
import type { AnomalyFlag } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import loadHome from '../../household/loadHome';
import { useAccount, useHousehold } from '../../household/session';
import { formatRwandanPhone } from '../../utils/phone';
import InstallApp from '../../pwa/InstallApp';
import PushOptIn from '../../pwa/PushOptIn';
import styles from './CustomerHome.module.css';

/** Mwaramutse / Mwiriwe: by the hour of the day on this phone. */
function greetingKey(hour = new Date().getHours()): string {
  if (hour < 12) return 'home.greeting.morning';
  if (hour < 18) return 'home.greeting.afternoon';
  return 'home.greeting.evening';
}

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

function QuickAction({ to, icon, label, hint, tone }: { to: string; icon: IconName; label: string; hint: string; tone: string }) {
  return (
    <Link to={to} className={`${styles.quick} ${styles[tone]}`}>
      <span className={styles.quickIcon}>
        <Icon name={icon} size={22} />
      </span>
      <span className={styles.quickText}>
        <span className={styles.quickLabel}>{label}</span>
        <span className={styles.quickHint}>{hint}</span>
      </span>
      <Icon name="chevronRight" size={18} className={styles.quickArrow} />
    </Link>
  );
}

function CustomerHome() {
  const account = useAccount();
  const household = useHousehold();
  const customerId = account.customer_id;
  const meterId = account.meter_id ?? '';
  const { t, rwf, date, month, monthShort, volume } = useI18n();
  const navigate = useNavigate();
  const home = useRequest(loadHome, { immediate: true, args: [customerId, meterId] });

  if (home.status !== 'success') {
    return (
      <Screen title={t(greetingKey())} nav>
        <RequestState status={home.status} error={home.error} onRetry={home.retry} />
      </Screen>
    );
  }

  const { customer, newestBill, highUse, bills, decision } = home.data;
  const checking = home.data.checking || customer.reading_pending;
  const opensOn = customer.next_reading_from;
  const due = newestBill && newestBill.payment_status !== 'paid' ? newestBill : null;
  const canRead = !checking && !opensOn;
  const usage = bills
    .slice(0, 6)
    .reverse()
    .map((b) => ({ key: String(b.bill_id), label: monthShort(b.created_at), value: b.consumption_m3 }));

  return (
    <Screen
      step={customer.name}
      title={t(greetingKey())}
      nav
    >
      {decision && <DecisionBanner flag={decision} meterId={meterId} />}

      {/* What to do now. */}
      <section className={`${styles.hero} imigongo-band`} aria-labelledby="status-title">
        {due ? (
          <>
            <div className={styles.heroTop}>
              <p id="status-title" className={styles.heroLabel}>
                {t('home.billFor', { month: month(due.created_at) })}
              </p>
              <span className="chip chip-held">{t('bill.unpaid')}</span>
            </div>
            <p className={`${styles.heroAmount} amount`}>{rwf(due.amount_due)}</p>
            <p className={styles.heroNote}>{t('home.usedThisPeriod', { volume: volume(due.consumption_m3) })}</p>
            <div className={styles.heroActions}>
              <Button icon="wallet" onClick={() => navigate(`/payment?bill=${due.bill_id}`)}>
                {t('pay.action', { amount: rwf(due.amount_due) })}
              </Button>
              <Button variant="secondary" onClick={() => navigate(`/bill?id=${due.bill_id}`)}>
                {t('home.seeBill')}
              </Button>
            </div>
          </>
        ) : checking ? (
          <div className={styles.heroState}>
            <span className={`${styles.stateIcon} ${styles.held}`}>
              <Icon name="clock" size={26} />
            </span>
            <div>
              <h2 id="status-title" className={styles.heroTitle}>{t('home.checkingTitle')}</h2>
              <p className={styles.heroNote}>{t('home.checkingBody')}</p>
            </div>
          </div>
        ) : opensOn ? (
          <div className={styles.heroState}>
            <span className={`${styles.stateIcon} ${styles.ok}`}>
              <Icon name="check" size={26} />
            </span>
            <div>
              <h2 id="status-title" className={styles.heroTitle}>{t('home.readingInTitle')}</h2>
              <p className={styles.heroNote}>{t('home.readingInBody', { date: date(opensOn) })}</p>
            </div>
          </div>
        ) : (
          <div className={styles.heroState}>
            <span className={`${styles.stateIcon} ${styles.brand}`}>
              <Icon name="camera" size={26} />
            </span>
            <div>
              <h2 id="status-title" className={styles.heroTitle}>{t('home.readPromptTitle')}</h2>
              <p className={styles.heroNote}>{t('home.readPrompt')}</p>
            </div>
            <Button icon="camera" onClick={() => navigate('/submit/camera')} className={styles.heroButton}>
              {t('home.read')}
            </Button>
          </div>
        )}
      </section>

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

      <div className={styles.grid}>
        <nav className={styles.quickList} aria-label={t('home.quickTitle')}>
          {canRead && due && (
            <QuickAction to="/submit/camera" icon="camera" tone="brand" label={t('home.read')} hint={t('home.quick.readHint')} />
          )}
          <QuickAction to="/history" icon="bills" tone="clay" label={t('nav.bills')} hint={t('home.quick.billsHint')} />
          <QuickAction to="/messages" icon="messages" tone="ok" label={t('nav.messages')} hint={t('home.quick.messagesHint')} />
        </nav>

        <section className={`panel ${styles.usage}`} aria-labelledby="usage-title">
          <div className={styles.cardHead}>
            <h2 id="usage-title" className="panel-title">{t('home.usageTitle')}</h2>
            {customer.avg_consumption != null && (
              <span className="chip">{t('home.usageAverage', { volume: volume(customer.avg_consumption) })}</span>
            )}
          </div>
          {usage.length > 0 ? (
            <UsageChart
              points={usage}
              format={(v) => volume(v)}
              title={t('home.usageTitle')}
              monthHeader={t('home.usageMonth')}
              valueHeader={t('home.usageVolume')}
            />
          ) : (
            <p className="text-secondary">{t('home.usageEmpty')}</p>
          )}
        </section>

        <section className={`panel ${styles.meter}`} aria-labelledby="meter-title">
          <div className={styles.cardHead}>
            <h2 id="meter-title" className="panel-title">{t('home.meterTitle')}</h2>
            <span className="chip code">{customer.meter_id}</span>
          </div>
          <dl className={styles.facts}>
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
            {customer.sector && (
              <div className={styles.fact}>
                <dt>{t('home.sector')}</dt>
                <dd>{customer.sector}</dd>
              </div>
            )}
          </dl>
        </section>

        <section className={`panel ${styles.account}`} aria-label={t('home.signedInTitle')}>
          <div className={styles.accountRow}>
            <span className={styles.avatar} aria-hidden="true">
              <Icon name="user" size={20} />
            </span>
            <p className="text-small">{t('home.signedInAs', { phone: formatRwandanPhone(household.phone) })}</p>
          </div>
          <PushOptIn />
          <div className={styles.accountActions}>
            <InstallApp />
            {household.accounts.length > 1 && (
              <Button variant="text" onClick={() => navigate('/sign-in?switch=1')}>
                {t('home.switchMeter')}
              </Button>
            )}
            <Button variant="text" icon="logout" onClick={household.signOut}>
              {t('home.signOut')}
            </Button>
          </div>
        </section>
      </div>
    </Screen>
  );
}

export default CustomerHome;
