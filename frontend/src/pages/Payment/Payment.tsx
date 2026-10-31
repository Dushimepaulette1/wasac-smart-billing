/**
 * @file Payment.tsx
 * @description Pay one bill with MTN Mobile Money.
 * The button says the amount ("Pay RWF 12,401") and becomes "Paid".
 * If the connection drops mid-payment we cannot know whether it went
 * through, so the household is told to check their bills before trying
 * again rather than being told they were not charged.
 *
 * With MTN Mobile Money keys, paying sends a PIN prompt to the household's
 * phone: the page waits ("Approve the payment on your phone") and checks
 * GET /payments/{id} every few seconds until MTN answers. Without keys the
 * payment is simulated; a test payment says so on the receipt.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import RequestState, { errorMessage } from '../../components/RequestState/RequestState';
import Progress from '../../components/Progress/Progress';
import useRequest from '../../api/useRequest';
import { api, ApiError } from '../../api/client';
import type { BillSummary, Payment as PaymentAttempt } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { localDateIso } from '../../i18n/format';
import { formatRwandanPhone } from '../../utils/phone';
import { useAccount } from '../../household/session';
import styles from './Payment.module.css';
import { amountOwed } from '../../utils/bill';

interface PaymentView {
  bill: BillSummary;
  /** The account's MTN Mobile Money number. */
  phone: string;
}

interface Receipt {
  /** Null when the bill had already been paid (no new transaction). */
  transactionId: string | null;
  at: string;
  /** Sandbox or simulated: no real money moved. */
  test: boolean;
}

/** How often, and how long, to ask whether the household approved the MoMo prompt. */
const POLL_MS = 3000;
const POLL_LIMIT = 40; // 2 minutes

async function loadPayment(customerId: string, billId: number): Promise<PaymentView> {
  const [bills, customer] = await Promise.all([api.getBills(customerId), api.getCustomer(customerId)]);
  const bill = bills.find((b) => b.bill_id === billId);
  if (!bill) throw new ApiError('notFound', 404, `Bill ${billId} not found`);
  return { bill, phone: customer.phone };
}

function Payment() {
  const account = useAccount();
  const customerId = account.customer_id;
  const { t, rwf, month, date } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const billId = Number(params.get('bill'));
  const load = useRequest(loadPayment);
  const { run } = load;
  // momopay: dial WASAC's MoMo Pay code, then give the transaction ID; checking: WASAC is checking it.
  const [state, setState] = useState<'ready' | 'paying' | 'waiting' | 'paid' | 'unsure' | 'failed' | 'declined' | 'momopay' | 'checking'>('ready');
  const [txId, setTxId] = useState('');
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState<PaymentAttempt | null>(null);
  const polls = useRef(0);

  /** Act on MTN's answer (or the simulated one). */
  const settle = (p: PaymentAttempt) => {
    setAttempt(p);
    if (p.status === 'successful') {
      setReceipt({ transactionId: p.already_paid ? null : p.transaction_id, at: localDateIso(), test: p.provider !== 'momo' });
      setState('paid');
    } else if (p.status === 'failed') {
      setState('declined');
    } else if (p.provider === 'momo_pay') {
      setState(p.transaction_id ? 'checking' : 'momopay');
    } else {
      setState('waiting');
    }
  };

  // Waiting for the household to approve the prompt on their phone: ask every few seconds.
  useEffect(() => {
    if (state !== 'waiting' || !attempt) return undefined;
    const timer = window.setTimeout(async () => {
      polls.current += 1;
      if (polls.current > POLL_LIMIT) {
        setState('unsure');
        return;
      }
      try {
        settle(await api.getPayment(attempt.id));
      } catch {
        setAttempt({ ...attempt }); // a dropped check: try again on the next tick
      }
    }, POLL_MS);
    return () => window.clearTimeout(timer);
    // settle only sets state; the next tick is scheduled by the new attempt object.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, attempt]);

  useEffect(() => {
    run(customerId, billId);
  }, [run, billId]);

  if (load.status !== 'success') {
    return (
      <Screen title={t('pay.title')} back>
        <RequestState status={load.status} error={load.error} onRetry={load.retry} />
      </Screen>
    );
  }

  const { bill, phone } = load.data;
  const amount = rwf(amountOwed(bill));
  const alreadyPaid = bill.payment_status === 'paid' && state === 'ready';

  const pay = async () => {
    setState('paying');
    setError(null);
    polls.current = 0;
    try {
      settle(await api.payBill(bill.bill_id));
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
          <dl className={`panel ${styles.receipt}`}>
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
        {receipt?.test && <p className="text-small">{t('pay.testMode')}</p>}
      </Screen>
    );
  }

  if (state === 'momopay' && attempt) {
    const code = attempt.ussd_code ?? null;
    const sendId = async (e: FormEvent) => {
      e.preventDefault();
      const id = txId.trim();
      if (!/^[A-Za-z0-9.-]{4,40}$/.test(id)) return setError(new ApiError('invalid'));
      setSending(true);
      setError(null);
      try {
        settle(await api.submitPaymentReference(attempt.id, id));
      } catch (err) {
        setError(err);
      } finally {
        setSending(false);
      }
    };
    const copy = async () => {
      try {
        await navigator.clipboard.writeText(code ?? '');
        setCopied(true);
      } catch {
        // No clipboard: the code is on screen to type.
      }
    };
    return (
      <Screen title={t('pay.momoPayTitle')} lede={<p>{t('pay.momoPayLede', { amount })}</p>} back>
        <section className={`panel ${styles.panel}`} aria-labelledby="dial-title">
          <p id="dial-title" className={styles.stepLabel}>{t('pay.momoPayStep1')}</p>
          {code ? (
            <>
              <a className={styles.ussd} href={`tel:${code.replace(/#/g, '%23')}`}>
                <span className="num">{code}</span>
              </a>
              <div className={styles.codeActions}>
                <Button variant="secondary" icon="phone" href={`tel:${code.replace(/#/g, '%23')}`}>
                  {t('pay.momoPayDial')}
                </Button>
                <Button variant="text" onClick={copy}>
                  {copied ? t('pay.momoPayCopied') : t('pay.momoPayCopy')}
                </Button>
              </div>
            </>
          ) : (
            <p>{t('pay.momoPayNoCode')}</p>
          )}
          <dl className={styles.receipt}>
            <div className={styles.line}>
              <dt className="text-secondary">{t('pay.amount')}</dt>
              <dd className="num">{amount}</dd>
            </div>
            <div className={styles.line}>
              <dt className="text-secondary">{t('pay.momoPayReference')}</dt>
              <dd className="code">{attempt.reference ?? bill.bill_id}</dd>
            </div>
          </dl>
          <p className="text-small text-secondary">{t('pay.bankNote')}</p>
        </section>

        <form className={`panel ${styles.panel}`} onSubmit={sendId} noValidate>
          <label htmlFor="momo-tx" className={styles.stepLabel}>{t('pay.momoPayStep2')}</label>
          <p className="text-small text-secondary">{t('pay.momoPayStep2Hint')}</p>
          {Boolean(error) && (
            <Notice tone="error" live>
              {error instanceof ApiError && error.kind === 'invalid' ? t('pay.momoPayBadId') : errorMessage(t, error)}
            </Notice>
          )}
          <input
            id="momo-tx"
            className={styles.txInput}
            value={txId}
            onChange={(e) => setTxId(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            inputMode="text"
          />
          <Button type="submit" loading={sending}>
            {t('pay.momoPaySubmit')}
          </Button>
        </form>
      </Screen>
    );
  }

  if (state === 'checking' && attempt) {
    return (
      <Screen
        title={t('pay.checkingTitle')}
        action={
          <Button fullWidth onClick={() => navigate('/home')}>
            {t('action.backHome')}
          </Button>
        }
      >
        <Notice tone="held" live title={t('pay.checkingTitle')}>
          {t('pay.checkingBody', { id: attempt.transaction_id ?? '', amount })}
        </Notice>
      </Screen>
    );
  }

  if (state === 'waiting') {
    return (
      <Screen title={t('pay.waitingTitle')} lede={<p>{t('pay.waitingBody', { phone: formatRwandanPhone(phone), amount })}</p>}>
        <Progress label={t('pay.waitingCheck')} />
        {attempt?.provider === 'momo_sandbox' && <p className="text-small">{t('pay.sandboxNote')}</p>}
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
          {attempt ? t('pay.stillWaiting') : t('pay.unsure')}
        </Notice>
      )}
      {state === 'declined' && (
        <Notice tone="error" live title={t('pay.declinedTitle')}>
          {t('pay.declinedBody')}
          {attempt?.reason ? ` (${attempt.reason})` : ''}
        </Notice>
      )}
      {state === 'failed' && (
        <Notice tone="error" live>
          {errorMessage(t, error)}
        </Notice>
      )}

      <section className={`panel ${styles.panel}`}>
        <p className="text-secondary">{t('bill.title', { month: month(bill.created_at) })}</p>
        <p className={`${styles.amount} num`}>{amount}</p>
        <p className={styles.from}>{t('pay.from', { phone: formatRwandanPhone(phone) })}</p>
      </section>
    </Screen>
  );
}

export default Payment;
