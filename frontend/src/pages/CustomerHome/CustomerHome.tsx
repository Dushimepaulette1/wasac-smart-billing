/**
 * @file CustomerHome.tsx
 * @description Home leads with the household's next action, in words:
 * pay the bill that is due, or read the meter. No big-number hero and no
 * counter here; the counter belongs to readings.
 */

import { Link, useNavigate } from 'react-router-dom';
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
import styles from './CustomerHome.module.css';

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

  const { customer, newestBill, checking, highUse } = home.data;
  const due = newestBill && newestBill.payment_status !== 'paid' ? newestBill : null;
  const readMeter = () => navigate('/submit/camera');

  // While a reading waits for an officer, a new one is not asked for: the household waits.
  const readButton = checking ? null : (
    <Button variant={due ? 'text' : undefined} fullWidth={!due} icon="camera" onClick={readMeter}>
      {t('home.read')}
    </Button>
  );
  const action = due ? (
    <>
      {readButton}
      <Button fullWidth onClick={() => navigate(`/payment?bill=${due.bill_id}`)}>
        {t('pay.action', { amount: rwf(due.amount_due) })}
      </Button>
    </>
  ) : (
    readButton
  );

  let title = t('home.readPrompt');
  if (due) title = t('home.billDue', { month: month(due.created_at), amount: rwf(due.amount_due) });
  else if (checking) title = t('home.checkingTitle');

  return (
    <Screen
      step={customer.name}
      title={title}
      lede={
        due ? (
          <Link to={`/bill?id=${due.bill_id}`} className={styles.link}>
            {t('home.seeBill')}
          </Link>
        ) : checking ? (
          <p>{t('home.checkingBody')}</p>
        ) : null
      }
      nav
      action={action}
    >
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
        <div className={styles.signedInActions}>
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
