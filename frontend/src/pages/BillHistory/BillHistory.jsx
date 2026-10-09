/**
 * @file BillHistory.jsx
 * @description All the household's bills, newest first. Each row opens
 * the bill; paying happens there, so the list stays a plain list.
 */

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { api } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { CUSTOMER_ID } from '../../config';
import styles from './BillHistory.module.css';

function BillHistory() {
  const { t, rwf, volume, monthYear, date } = useI18n();
  const navigate = useNavigate();
  const bills = useRequest(api.getBills, { immediate: true, args: [CUSTOMER_ID] });

  const empty = bills.status === 'success' && bills.data.length === 0;

  // Normally one bill a month; if two share a month, name them by date.
  const label = (bill) => {
    const month = bill.created_at.slice(0, 7);
    const shared = bills.data.filter((b) => b.created_at.slice(0, 7) === month).length > 1;
    return shared ? date(bill.created_at) : monthYear(bill.created_at);
  };

  return (
    <Screen
      title={t('history.title')}
      nav
      action={
        empty ? (
          <Button fullWidth icon="camera" onClick={() => navigate('/submit/camera')}>
            {t('home.read')}
          </Button>
        ) : null
      }
    >
      {bills.status !== 'success' && (
        <RequestState status={bills.status} error={bills.error} onRetry={bills.retry} />
      )}

      {empty && <p className="measure">{t('history.empty')}</p>}

      {bills.status === 'success' && bills.data.length > 0 && (
        <ul className={styles.list}>
          {bills.data.map((bill) => {
            const paid = bill.payment_status === 'paid';
            return (
              <li key={bill.bill_id}>
                <Link to={`/bill?id=${bill.bill_id}`} className={styles.row}>
                  <span className={`${styles.month} num`}>{label(bill)}</span>
                  <span className={`${styles.amount} num`}>{rwf(bill.amount_due)}</span>
                  <span className="num text-secondary">{volume(bill.consumption_m3)}</span>
                  <span className={`${styles.status} ${paid ? '' : styles.unpaid}`}>
                    {paid ? t('bill.paid') : t('bill.unpaid')}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Screen>
  );
}

export default BillHistory;
