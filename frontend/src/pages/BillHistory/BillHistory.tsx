/**
 * @file BillHistory.tsx
 * @description All the household's bills, newest first. Each row opens
 * the bill; paying happens there, so the list stays a plain list.
 */

import { Link, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { api } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { useAccount } from '../../household/session';
import type { BillSummary } from '../../api/types';
import { readingIsWaiting, useHouseholdFlags } from '../../household/status';
import styles from './BillHistory.module.css';

function BillHistory() {
  const account = useAccount();
  const customerId = account.customer_id;
  const { t, rwf, volume, monthYear, date } = useI18n();
  const navigate = useNavigate();
  const bills = useRequest(api.getBills, { immediate: true, args: [customerId] });

  const list: BillSummary[] = bills.status === 'success' ? bills.data : [];
  const empty = bills.status === 'success' && list.length === 0;
  // A reading is waiting for an officer: say so instead of asking for another one.
  const waiting = readingIsWaiting(useHouseholdFlags());

  // Normally one bill a month; if two share a month, name them by date.
  const label = (bill: BillSummary) => {
    const month = bill.created_at.slice(0, 7);
    const shared = list.filter((b) => b.created_at.slice(0, 7) === month).length > 1;
    return shared ? date(bill.created_at) : monthYear(bill.created_at);
  };

  return (
    <Screen
      title={t('history.title')}
      nav
      action={
        empty && !waiting ? (
          <Button fullWidth icon="camera" onClick={() => navigate('/submit/camera')}>
            {t('home.read')}
          </Button>
        ) : null
      }
    >
      {bills.status !== 'success' && (
        <RequestState status={bills.status} error={bills.error} onRetry={bills.retry} />
      )}

      {empty && <p className="measure">{waiting ? t('history.checking') : t('history.empty')}</p>}

      {list.length > 0 && (
        <ul className={styles.list}>
          {list.map((bill, i) => {
            const paid = bill.payment_status === 'paid';
            return (
              <li key={bill.bill_id} className={`enter enter-${Math.min(i + 1, 4)}`}>
                <Link to={`/bill?id=${bill.bill_id}`} className={styles.row}>
                  <span className={`${styles.icon} ${paid ? styles.paidIcon : ''}`} aria-hidden="true">
                    <Icon name={paid ? 'check' : 'bills'} size={22} />
                  </span>
                  <span className={`${styles.month} num`}>{label(bill)}</span>
                  <span className={`${styles.amount} num`}>{rwf(bill.amount_due)}</span>
                  <span className={`${styles.volume} num`}>{volume(bill.consumption_m3)}</span>
                  <span className={`${styles.status} chip ${paid ? 'chip-ok' : 'chip-held'}`}>
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
