/**
 * @file BillDisplay.jsx
 * @description One bill: how much water, what it costs and why, and the
 * last months for comparison. Money is plain bold text, never the counter;
 * the counter appears once, for this bill's meter reading.
 */

import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import loadBill from '../../household/loadBill';
import { CUSTOMER_ID } from '../../config';
import styles from './BillDisplay.module.css';

function UsageBars({ history, currentId }) {
  const { t, month, volume } = useI18n();
  const max = Math.max(...history.map((b) => b.consumption_m3), 1);
  return (
    <section className={styles.usage} aria-labelledby="usage-title">
      <h2 id="usage-title" className="text-body">
        {t('bill.usageTitle')}
      </h2>
      <ol className={styles.bars}>
        {history.map((b) => {
          const current = b.bill_id === currentId;
          return (
            <li key={b.bill_id} className={`${styles.barRow} ${current ? styles.current : ''}`}>
              <span>{month(b.created_at)}</span>
              <span className={styles.track} aria-hidden="true">
                <span className={styles.bar} style={{ width: `${(b.consumption_m3 / max) * 100}%` }} />
              </span>
              <span className="num">{volume(b.consumption_m3)}</span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function BillDisplay() {
  const { t, locale, rwf, volume, date, month } = useI18n();
  const navigate = useNavigate();
  const labels = useCounterLabels();
  const [params] = useSearchParams();
  const idParam = params.get('id');
  const billId = idParam ? Number(idParam) : null;
  const request = useRequest(loadBill);
  const { run } = request;

  // Load on arrival and again when moving to another bill on this screen.
  useEffect(() => {
    run(CUSTOMER_ID, billId);
  }, [run, billId]);

  if (request.status !== 'success') {
    return (
      <Screen title={t('bill.titleLoading')} back nav>
        <RequestState status={request.status} error={request.error} onRetry={request.retry} />
      </Screen>
    );
  }

  const { bill, tiers, serviceCharge, periodStart, reading, previousReading, history } = request.data;
  const paid = bill.payment_status === 'paid';
  const water = bill.amount_due - serviceCharge;

  return (
    <Screen
      title={t('bill.title', { month: month(bill.created_at) })}
      back
      nav
      action={
        paid ? null : (
          <Button fullWidth onClick={() => navigate(`/payment?bill=${bill.bill_id}`)}>
            {t('pay.action', { amount: rwf(bill.amount_due) })}
          </Button>
        )
      }
    >
      <div>
        <p className="text-lead">{t('bill.used', { volume: volume(bill.consumption_m3) })}</p>
        <p className="text-secondary">
          {periodStart
            ? t('bill.period', { from: date(periodStart), to: date(bill.created_at) })
            : t('bill.issued', { date: date(bill.created_at) })}
        </p>
      </div>

      {reading && (
        <section className={styles.reading} aria-labelledby="reading-title">
          <h2 id="reading-title" className="text-body">
            {t('bill.thisReading')}
          </h2>
          <MeterCounter cells={reading} labels={labels} locale={locale} />
          <p className={styles.previous}>
            <span className="text-secondary">{t('bill.lastReading')}</span>
            <span className="num">
              {formatReading(cellsFromCubicMetres(previousReading), locale)} {labels.cubicMetres}
            </span>
          </p>
        </section>
      )}

      <section className={styles.panel} aria-labelledby="cost-title">
        <h2 id="cost-title" className="visually-hidden">
          {t('bill.costTitle')}
        </h2>
        <dl className={styles.lines}>
          <div className={styles.line}>
            <dt>{t('bill.water')}</dt>
            <dd className="num">{rwf(water)}</dd>
          </div>
          <div className={styles.line}>
            <dt>{t('bill.service')}</dt>
            <dd className="num">{rwf(serviceCharge)}</dd>
          </div>
          <div className={`${styles.line} ${styles.total}`}>
            <dt>{t('bill.total')}</dt>
            <dd className="num">{rwf(bill.amount_due)}</dd>
          </div>
        </dl>

        <p className={styles.status}>
          {paid ? (
            <>
              <Icon name="check" />
              <span>{t('bill.paid')}</span>
            </>
          ) : (
            <span>{t('bill.unpaid')}</span>
          )}
        </p>

        <details className={styles.details}>
          <summary>{t('bill.howTitle')}</summary>
          <ul className={styles.tiers}>
            {tiers.map((tier) => (
              <li key={tier.rate} className={styles.line}>
                <span>{t('bill.tierLine', { volume: volume(tier.units), rate: rwf(tier.rate) })}</span>
                <span className="num">{rwf(tier.amount)}</span>
              </li>
            ))}
          </ul>
          <p className="text-small text-secondary">{t('bill.howNote')}</p>
        </details>
      </section>

      {history.length > 1 && <UsageBars history={history} currentId={bill.bill_id} />}
    </Screen>
  );
}

export default BillDisplay;
