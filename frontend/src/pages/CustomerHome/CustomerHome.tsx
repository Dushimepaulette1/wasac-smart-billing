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
import LanguageSwitcher from '../../components/LanguageSwitcher/LanguageSwitcher';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import loadHome from '../../household/loadHome';
import { CUSTOMER_ID, METER_ID } from '../../config';
import styles from './CustomerHome.module.css';

function CustomerHome() {
  const { t, locale, rwf, date, month } = useI18n();
  const navigate = useNavigate();
  const home = useRequest(loadHome, { immediate: true, args: [CUSTOMER_ID, METER_ID] });

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

  const action = due ? (
    <>
      <Button variant="text" icon="camera" onClick={readMeter}>
        {t('home.read')}
      </Button>
      <Button fullWidth onClick={() => navigate(`/payment?bill=${due.bill_id}`)}>
        {t('pay.action', { amount: rwf(due.amount_due) })}
      </Button>
    </>
  ) : (
    <Button fullWidth icon="camera" onClick={readMeter}>
      {t('home.read')}
    </Button>
  );

  return (
    <Screen
      step={customer.name}
      title={due ? t('home.billDue', { month: month(due.created_at), amount: rwf(due.amount_due) }) : t('home.readPrompt')}
      lede={
        due ? (
          <Link to={`/bill?id=${due.bill_id}`} className={styles.link}>
            {t('home.seeBill')}
          </Link>
        ) : customer.last_reading_date ? (
          <p>{t('home.lastRead', { date: date(customer.last_reading_date) })}</p>
        ) : null
      }
      nav
      action={action}
    >
      <div className="columns">
        <div className="stack">
          {checking && (
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

        <div className="stack">
          <section className="panel" aria-labelledby="meter-title">
            <h2 id="meter-title" className="panel-title">
              {t('home.meterTitle')}
            </h2>
            <dl className={styles.meter}>
              <div className={styles.line}>
                <dt className="text-secondary">{t('home.meter')}</dt>
                <dd className="code">{customer.meter_id}</dd>
              </div>
              <div className={styles.line}>
                <dt className="text-secondary">{t('home.lastReading')}</dt>
                <dd className="num">
                  {formatReading(cellsFromCubicMetres(customer.last_reading), locale)} {t('counter.cubicMetres')}
                </dd>
              </div>
              {customer.last_reading_date && (
                <div className={styles.line}>
                  <dt className="text-secondary">{t('home.lastReadOn')}</dt>
                  <dd className="num">{date(customer.last_reading_date)}</dd>
                </div>
              )}
            </dl>
          </section>
          <aside className="panel-quiet">
            <LanguageSwitcher variant="full" />
          </aside>
        </div>
      </div>
    </Screen>
  );
}

export default CustomerHome;
