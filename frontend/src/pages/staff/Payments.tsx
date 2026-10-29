/**
 * @file Payments.tsx
 * @description MoMo Pay payments waiting for an officer. A household that pays WASAC's MoMo Pay
 * code by USSD enters the transaction ID from MTN's SMS; the bill stays unpaid until an officer
 * finds that transaction in WASAC's MoMo merchant account (portal or statement) and confirms it
 * here, or declines it with a reason (the household gets an SMS and can pay again). Every
 * decision is in Activity. Bills paid more than once are listed too, for information.
 */

import { useState } from 'react';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState, { errorMessage } from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import type { PaymentToCheck } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { dateTime } from '../../staff/time';
import styles from '../../staff/staff.module.css';

function Payments() {
  const { t, rwf } = useI18n();
  const rows = useRequest(api.paymentsToCheck, { immediate: true, args: [] });
  const [done, setDone] = useState<number[]>([]);
  const [declining, setDeclining] = useState<number | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState<number | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  const act = async (row: PaymentToCheck, how: 'confirm' | 'decline') => {
    setBusy(row.id);
    setError(null);
    try {
      if (how === 'confirm') await api.confirmPayment(row.id);
      else await api.declinePayment(row.id, reason.trim());
      setDone((d) => [...d, row.id]);
      setDeclining(null);
      setReason('');
      setResult(t(how === 'confirm' ? 'staff.payments.confirmed' : 'staff.payments.declined', {
        name: row.customer_name, amount: rwf(row.amount),
      }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const list = rows.status === 'success' ? rows.data.filter((r) => !done.includes(r.id)) : [];

  return (
    <StaffLayout title={t('staff.nav.payments')} lede={t('staff.payments.lede')}>
      <div className={styles.stack}>
        {result && <Notice tone="done" live>{result}</Notice>}
        {Boolean(error) && <Notice tone="error" live>{errorMessage(t, error)}</Notice>}
        <section className="panel" aria-label={t('staff.nav.payments')}>
          <div className={styles.filters}>
            <Button variant="secondary" onClick={rows.retry} loading={rows.status === 'loading'}>
              {t('staff.sms.refresh')}
            </Button>
          </div>
          {rows.status !== 'success' ? (
            <RequestState status={rows.status} error={rows.error} onRetry={rows.retry} />
          ) : list.length === 0 ? (
            <p className={styles.empty}>{t('staff.payments.none')}</p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">{t('staff.payments.household')}</th>
                    <th scope="col" className={styles.right}>{t('pay.amount')}</th>
                    <th scope="col">{t('staff.payments.transaction')}</th>
                    <th scope="col">{t('staff.payments.sent')}</th>
                    <th scope="col">{t('staff.payments.check')}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => (
                    <tr key={r.id}>
                      <td>
                        {r.customer_name}
                        <span className={`${styles.cellSub} code`}>{r.meter_id} · {t('staff.payments.bill', { id: r.bill_id })}</span>
                      </td>
                      <td data-label={t('pay.amount')} className={`${styles.right} num`}>{rwf(r.amount)}</td>
                      <td data-label={t('staff.payments.transaction')} className="code">{r.transaction_id}</td>
                      <td data-label={t('staff.payments.sent')} className="num">{dateTime(r.submitted_at)}</td>
                      <td data-label={t('staff.payments.check')}>
                        {r.kind === 'paid_twice' ? (
                          <p className="text-small">{t('staff.payments.paidTwice')}</p>
                        ) : declining === r.id ? (
                          <div className={styles.form}>
                            <label className={styles.filter}>
                              {t('staff.payments.reason')}
                              <input className={styles.search} value={reason} onChange={(e) => setReason(e.target.value)} />
                            </label>
                            <div className={styles.rowActions}>
                              <Button variant="secondary" disabled={reason.trim().length < 3} loading={busy === r.id}
                                onClick={() => act(r, 'decline')}>
                                {t('staff.payments.decline')}
                              </Button>
                              <Button variant="text" onClick={() => setDeclining(null)}>{t('action.cancel')}</Button>
                            </div>
                          </div>
                        ) : (
                          <div className={styles.rowActions}>
                            <Button loading={busy === r.id} onClick={() => act(r, 'confirm')}>
                              {t('staff.payments.confirm')}
                            </Button>
                            <Button variant="text" onClick={() => { setDeclining(r.id); setReason(''); }}>
                              {t('staff.payments.notFound')}
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="text-small text-secondary">{t('staff.payments.how')}</p>
        </section>
      </div>
    </StaffLayout>
  );
}

export default Payments;
