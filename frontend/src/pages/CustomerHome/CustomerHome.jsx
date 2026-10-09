/**
 * @file CustomerHome.jsx
 * @description Home leads with the household's next action, in words:
 * pay the bill that is due, or read the meter. No big-number hero and no
 * counter here; the counter belongs to readings.
 */

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { useI18n, LOCALES, LANGUAGE_NAMES } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import loadHome from '../../household/loadHome';
import { CUSTOMER_ID, METER_ID } from '../../config';
import styles from './CustomerHome.module.css';

function LanguagePicker() {
  const { t, locale, setLocale } = useI18n();
  return (
    <label className={styles.language}>
      <span>{t('language.label')}</span>
      <select value={locale} onChange={(e) => setLocale(e.target.value)} className={styles.select}>
        {LOCALES.map((code) => (
          <option key={code} value={code} lang={code}>
            {LANGUAGE_NAMES[code]}
          </option>
        ))}
      </select>
    </label>
  );
}

function CustomerHome() {
  const { t, locale, rwf, date, month } = useI18n();
  const navigate = useNavigate();
  const home = useRequest(loadHome, { immediate: true, args: [CUSTOMER_ID, METER_ID] });

  if (home.status !== 'success') {
    return (
      <Screen title={t('app.name')} nav>
        <RequestState status={home.status} error={home.error} onRetry={home.retry} />
        <LanguagePicker />
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
    <Screen title={customer.name} nav action={action}>
      <section className={styles.next}>
        {due ? (
          <>
            <p className="text-lead">
              {t('home.billDue', { month: month(due.created_at), amount: rwf(due.amount_due) })}
            </p>
            <Link to={`/bill?id=${due.bill_id}`} className={styles.link}>
              {t('home.seeBill')}
            </Link>
          </>
        ) : (
          <>
            <p className="text-lead">{t('home.readPrompt')}</p>
            {customer.last_reading_date && (
              <p className="text-secondary">{t('home.lastRead', { date: date(customer.last_reading_date) })}</p>
            )}
          </>
        )}
      </section>

      {checking && (
        <Notice tone="held" title={t('home.checkingTitle')}>
          {t('home.checkingBody')}
        </Notice>
      )}

      {highUse && (
        <Notice
          tone="info"
          actions={
            <Button variant="text" onClick={() => navigate('/messages')}>
              {t('home.readMessage')}
            </Button>
          }
        >
          {t('home.highUse')}
        </Notice>
      )}

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
      </dl>

      <LanguagePicker />
    </Screen>
  );
}

export default CustomerHome;
