/**
 * @file BillCorrection.tsx
 * @description Supervisors and admins: correct a reading that was already billed. Nothing billed or
 * paid is changed: the effect on each bill is shown first, then recorded as an adjustment. If it
 * charges more, a different supervisor or admin approves it here. Every step is in Activity
 * (backend app/services/bill_corrections.py).
 */

import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import { useAuth } from '../../staff/auth';
import type { BillCorrection as Correction, BillSummary } from '../../api/types';
import type { HouseholdRow } from '../../staff/loadOverview';
import styles from '../../staff/staff.module.css';

interface BillCorrectionProps {
  households: HouseholdRow[];
  onCorrected: () => void;
}

function Lines({ correction }: { correction: Correction }) {
  const { t, rwf } = useI18n();
  return (
    <ul className="text-small">
      {correction.adjustments.map((a) => (
        <li key={a.bill_id}>
          {t('staff.bills.line', {
            id: a.bill_id, from: rwf(a.amount_before), to: rwf(a.amount_after),
            before: a.consumption_before.toFixed(3), after: a.consumption_after.toFixed(3),
          })}
        </li>
      ))}
    </ul>
  );
}

function BillCorrection({ households, onCorrected }: BillCorrectionProps) {
  const { t, rwf, date } = useI18n();
  const { user } = useAuth();
  const [customerId, setCustomerId] = useState('');
  const [bills, setBills] = useState<BillSummary[]>([]);
  const [readingId, setReadingId] = useState('');
  const [value, setValue] = useState('');
  const [reason, setReason] = useState('');
  const [preview, setPreview] = useState<Correction | null>(null);
  const [busy, setBusy] = useState(false);
  const [declining, setDeclining] = useState<number | null>(null);
  const [declineWhy, setDeclineWhy] = useState('');
  const [result, setResult] = useState<{ tone: 'error' | 'done'; text: string } | null>(null);
  const key = useRef(crypto.randomUUID());
  const waiting = useRequest(() => api.billCorrections('awaiting_approval'), { immediate: true, args: [] });
  const householdField = useId();
  const billField = useId();
  const valueField = useId();
  const reasonField = useId();

  useEffect(() => {
    setBills([]);
    setReadingId('');
    setPreview(null);
    if (customerId) api.staffBills(customerId).then(setBills).catch((err) => setResult({ tone: 'error', text: errorMessage(t, err) }));
  }, [customerId, t]);

  const fail = (err: unknown) => setResult({ tone: 'error', text: errorMessage(t, err) });

  const show = async (e: FormEvent) => {
    e.preventDefault();
    if (!readingId || !value.trim() || reason.trim().length < 5) {
      setResult({ tone: 'error', text: t('staff.bills.incomplete') });
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      setPreview(await api.correctBill(customerId, Number(readingId), {
        corrected_reading: value.trim(), reason: reason.trim(), request_key: key.current, apply: false,
      }));
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setResult(null);
    try {
      const saved = await api.correctBill(customerId, Number(readingId), {
        corrected_reading: value.trim(), reason: reason.trim(), request_key: key.current, apply: true,
      });
      key.current = crypto.randomUUID();
      setResult({ tone: 'done', text: t(saved.status === 'applied' ? 'staff.bills.applied' : 'staff.bills.waiting') });
      setPreview(null);
      setValue('');
      setReason('');
      waiting.retry();
      onCorrected();
      setBills(await api.staffBills(customerId));
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const decide = async (id: number, how: 'approve' | 'decline') => {
    setBusy(true);
    setResult(null);
    try {
      await api.decideBillCorrection(id, how, how === 'decline' ? declineWhy.trim() : undefined);
      setResult({ tone: 'done', text: t(how === 'approve' ? 'staff.bills.approved' : 'staff.bills.declined') });
      setDeclining(null);
      setDeclineWhy('');
      onCorrected();
    } catch (err) {
      fail(err);
    } finally {
      waiting.retry();
      setBusy(false);
    }
  };

  const toDecide = waiting.status === 'success' ? waiting.data : [];

  return (
    <section className="panel" aria-labelledby="bills-title">
      <h2 id="bills-title" className="panel-title">{t('staff.bills.title')}</h2>
      <p className="text-small text-secondary">{t('staff.bills.lede')}</p>
      {result && <Notice tone={result.tone} live>{result.text}</Notice>}

      {toDecide.map((c) => (
        <div key={c.id} className={styles.stack}>
          <p>
            <strong>{t('staff.bills.toDecide', { name: c.customer_name ?? c.customer_id, by: c.requested_by })}</strong>{' '}
            {t('staff.bills.values', { from: c.value_before_m3.toFixed(3), to: c.corrected_value_m3.toFixed(3) })} · {c.reason}
          </p>
          <Lines correction={c} />
          {c.requested_by === user?.username ? (
            <p className="text-small text-secondary">{t('staff.bills.notYours')}</p>
          ) : declining === c.id ? (
            <div className={styles.form}>
              <label className={styles.filter}>
                {t('staff.bills.declineWhy')}
                <input className={styles.search} value={declineWhy} maxLength={200} onChange={(e) => setDeclineWhy(e.target.value)} />
              </label>
              <div className={styles.rowActions}>
                <Button variant="secondary" disabled={declineWhy.trim().length < 3} loading={busy} onClick={() => decide(c.id ?? 0, 'decline')}>
                  {t('staff.bills.decline')}
                </Button>
                <Button variant="text" onClick={() => setDeclining(null)}>{t('action.cancel')}</Button>
              </div>
            </div>
          ) : (
            <div className={styles.rowActions}>
              <Button loading={busy} onClick={() => decide(c.id ?? 0, 'approve')}>{t('staff.bills.approve')}</Button>
              <Button variant="text" onClick={() => setDeclining(c.id)}>{t('staff.bills.decline')}</Button>
            </div>
          )}
        </div>
      ))}

      <form className={styles.filters} onSubmit={show} noValidate>
        <div className={styles.filter}>
          <label htmlFor={householdField}>{t('staff.col.household')}</label>
          <select id={householdField} className={styles.select} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">{t('staff.correct.choose')}</option>
            {households.map((h) => <option key={h.customer_id} value={h.customer_id}>{h.name} · {h.meter_id}</option>)}
          </select>
        </div>
        <div className={styles.filter}>
          <label htmlFor={billField}>{t('staff.bills.bill')}</label>
          <select id={billField} className={styles.select} value={readingId} onChange={(e) => { setReadingId(e.target.value); setPreview(null); }}>
            <option value="">{t('staff.bills.chooseBill')}</option>
            {bills.filter((b) => b.reading_id).map((b) => (
              <option key={b.bill_id} value={b.reading_id ?? ''}>
                {date(b.created_at)} · {rwf(b.charges ?? b.amount_due)} · {b.consumption_m3} m³
              </option>
            ))}
          </select>
        </div>
        <div className={styles.filter}>
          <label htmlFor={valueField}>{t('staff.bills.value')}</label>
          <input id={valueField} className={styles.search} inputMode="decimal" placeholder="421.460" value={value}
            onChange={(e) => { setValue(e.target.value); setPreview(null); }} />
        </div>
        <div className={styles.filter}>
          <label htmlFor={reasonField}>{t('staff.correct.reason')}</label>
          <input id={reasonField} className={styles.search} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <Button type="submit" variant="secondary" loading={busy}>{t('staff.bills.preview')}</Button>
      </form>

      {preview && (
        <div className={styles.stack}>
          <Lines correction={preview} />
          <p>{t('staff.bills.net', { amount: `${preview.net_delta > 0 ? '+' : '−'}${rwf(Math.abs(preview.net_delta))}` })}</p>
          {preview.needs_approval && <p className="text-small">{t('staff.bills.needsApproval')}</p>}
          <Button loading={busy} onClick={save}>{t(preview.needs_approval ? 'staff.bills.ask' : 'staff.bills.apply')}</Button>
        </div>
      )}
    </section>
  );
}

export default BillCorrection;
