/**
 * @file Payment.tsx
 * @description Pay one bill with MTN Mobile Money.
 * The button says the amount ("Pay RWF 12,401") and becomes "Paid".
 * If the connection drops mid-payment we cannot know whether it went
 * through, so the household is told to check their bills before trying
 * again rather than being told they were not charged.
 *
 * Note: POST /bills/{id}/pay marks the bill paid and returns a transaction
 * id; there is no real MoMo prompt behind it yet, so none is promised here.
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import RequestState, { errorMessage } from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { api, ApiError } from '../../api/client';
import type { BillSummary } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { localDateIso } from '../../i18n/format';
import { formatRwandanPhone } from '../../utils/phone';
import { CUSTOMER_ID } from '../../config';
import styles from './Payment.module.css';

interface PaymentView {
  bill: BillSummary;
  /** The account's MTN Mobile Money number. */
  phone: string;
}

interface Receipt {
  /** Null when the bill had already been paid (no new transaction). */
  transactionId: string | null;
  at: string;
}

async function loadPayment(customerId: string, billId: number): Promise<PaymentView> {
  const [bills, customer] = await Promise.all([api.getBills(customerId), api.getCustomer(customerId)]);
  const bill = bills.find((b) => b.bill_id === billId);
  if (!bill) throw new ApiError('notFound', 404, `Bill ${billId} not found`);
  return { bill, phone: customer.phone };
}

function Payment() {
  const { t, rwf, month, date } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const billId = Number(params.get('bill'));
  const load = useRequest(loadPayment);
  const { run } = load;
  const [state, setState] = useState<'ready' | 'paying' | 'paid' | 'unsure' | 'failed'>('ready');
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    run(CUSTOMER_ID, billId);
  }, [run, billId]);

  if (load.status !== 'success') {
    return (
      <Screen title={t('pay.title')} back>
        <RequestState status={load.status} error={load.error} onRetry={load.retry} />
      </Screen>
    );
  }

  const { bill, phone } = load.data;
  const amount = rwf(bill.amount_due);
  const alreadyPaid = bill.payment_status === 'paid' && state === 'ready';

  const pay = async () => {
    setState('paying');
    setError(null);
    try {
      const result = await api.payBill(bill.bill_id);
      // "Already paid" responses carry no transaction id.
      setReceipt({ transactionId: 'transaction_id' in result ? result.transaction_id : null, at: localDateIso() });
      setState('paid');
    } catch (err) {
      setError(err);
      // No answer: the payment may or may not have gone through.
      setState(err instanceof ApiError && (err.kind === 'offline' || err.kind === 'timeout') ? 'unsure' : 'failed');
    }
  };

  if (state === 'paid' || alreadyPaid) {
    return (
      <Screen
        title={t('pay.paidTitle')}
        action={
          <>
            <Button variant="text" onClick={() => navigate('/history')}>
              {t('pay.seeBills')}
            </Button>
            <Button fullWidth onClick={() => navigate('/home')}>
              {t('action.backHome')}
            </Button>
          </>
        }
      >
        <Notice tone="done" live title={alreadyPaid ? t('pay.already') : t('pay.paidBody', { amount })} />
        {receipt && (
          <dl className={styles.receipt}>
            <div className={styles.line}>
              <dt className="text-secondary">{t('pay.bill')}</dt>
              <dd>{t('bill.title', { month: month(bill.created_at) })}</dd>
            </div>
            <div className={styles.line}>
              <dt className="text-secondary">{t('pay.amount')}</dt>
              <dd className="num">{amount}</dd>
            </div>
            <div className={styles.line}>
              <dt className="text-secondary">{t('pay.date')}</dt>
              <dd className="num">{date(receipt.at)}</dd>
            </div>
            {receipt.transactionId && (
              <div className={styles.line}>
                <dt className="text-secondary">{t('pay.transaction')}</dt>
                <dd className="code">{receipt.transactionId}</dd>
              </div>
            )}
          </dl>
        )}
      </Screen>
    );
  }

  return (
    <Screen
      title={t('pay.title')}
      back
      action={
        state === 'unsure' ? (
          <>
            <Button variant="text" onClick={pay}>
              {t('action.retry')}
            </Button>
            <Button fullWidth onClick={() => navigate('/history')}>
              {t('pay.seeBills')}
            </Button>
          </>
        ) : (
          <Button fullWidth onClick={pay} loading={state === 'paying'}>
            {state === 'paying' ? t('pay.paying') : t('pay.action', { amount })}
          </Button>
        )
      }
    >
      {state === 'unsure' && (
        <Notice tone="error" live>
          {t('pay.unsure')}
        </Notice>
      )}
      {state === 'failed' && (
        <Notice tone="error" live>
          {errorMessage(t, error)}
        </Notice>
      )}

      <section className={styles.panel}>
        <p className="text-secondary">{t('bill.title', { month: month(bill.created_at) })}</p>
        <p className={`${styles.amount} num`}>{amount}</p>
      </section>

      <p className="measure">{t('pay.from', { phone: formatRwandanPhone(phone) })}</p>
    </Screen>
  );
}

export default Payment;
