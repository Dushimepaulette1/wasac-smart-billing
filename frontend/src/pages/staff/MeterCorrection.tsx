/**
 * @file MeterCorrection.tsx
 * @description Supervisors and admins: set a meter's starting reading when the
 * record is wrong (a replaced meter, or wrong data). The next bill is measured
 * from it, so a different supervisor or admin must approve the change, unless
 * the meter has no starting value yet. Every step is in Activity (backend
 * app/services/meter_correction_requests.py).
 */

import { useId, useState, type FormEvent } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import useRequest from '../../api/useRequest';
import { useAuth } from '../../staff/auth';
import { useI18n } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import type { MeterCorrection as Correction } from '../../api/types';
import type { HouseholdRow } from '../../staff/loadOverview';
import styles from '../../staff/staff.module.css';

interface MeterCorrectionProps {
  households: HouseholdRow[];
  onCorrected: () => void;
}

const m3 = (value: number) => `${formatReading(cellsFromCubicMetres(value))} m³`;

function MeterCorrection({ households, onCorrected }: MeterCorrectionProps) {
  const { t } = useI18n();
  const { user } = useAuth();
  const waiting = useRequest(() => api.meterCorrections('awaiting_approval'), { immediate: true, args: [] });
  const [declining, setDeclining] = useState<number | null>(null);
  const [declineWhy, setDeclineWhy] = useState('');
  const [customerId, setCustomerId] = useState('');
  const [reading, setReading] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: 'error' | 'done'; text: string } | null>(null);
  const householdId = useId();
  const readingId = useId();
  const reasonId = useId();
  const chosen = households.find((h) => h.customer_id === customerId);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const value = Number(reading.replace(',', '.'));
    if (!chosen || !reading.trim() || !Number.isFinite(value) || value < 0 || value > 99999.999 || reason.trim().length < 3) {
      setResult({ tone: 'error', text: t('staff.correct.incomplete') });
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const updated = await api.correctMeter(chosen.customer_id, value, reason.trim());
      setResult({
        tone: 'done',
        text: t(updated.status === 'applied' ? 'staff.correct.done' : 'staff.correct.asked', {
          meter: updated.meter_id,
          reading: m3(updated.reading_m3),
        }),
      });
      setReading('');
      setReason('');
      waiting.retry();
      onCorrected();
    } catch (err) {
      const pending = err instanceof ApiError && err.kind === 'conflict';
      setResult({ tone: 'error', text: pending ? t('staff.correct.pending') : errorMessage(t, err) });
    } finally {
      setBusy(false);
    }
  };

  const decide = async (row: Correction, how: 'approve' | 'decline') => {
    setBusy(true);
    setResult(null);
    try {
      const done = await api.decideMeterCorrection(row.id, how, how === 'decline' ? declineWhy.trim() : undefined);
      setDeclining(null);
      setDeclineWhy('');
      setResult({
        tone: 'done',
        text: t(how === 'approve' ? 'staff.correct.done' : 'staff.correct.declined', { meter: done.meter_id, reading: m3(done.reading_m3) }),
      });
      onCorrected();
    } catch (err) {
      setResult({ tone: 'error', text: errorMessage(t, err) });
    } finally {
      setBusy(false);
      waiting.retry();
    }
  };

  const open = waiting.status === 'success' ? waiting.data : [];

  return (
    <section className="panel" aria-labelledby="correct-title">
      <h2 id="correct-title" className="panel-title">
        {t('staff.correct.title')}
      </h2>
      <p className="text-small text-secondary">{t('staff.correct.lede')}</p>
      {result && (
        <Notice tone={result.tone} live>
          {result.text}
        </Notice>
      )}
      <form className={styles.filters} onSubmit={submit} noValidate>
        <div className={styles.filter}>
          <label htmlFor={householdId}>{t('staff.col.household')}</label>
          <select id={householdId} className={styles.select} value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">{t('staff.correct.choose')}</option>
            {households.map((h) => (
              <option key={h.customer_id} value={h.customer_id}>
                {h.name} · {h.meter_id}
              </option>
            ))}
          </select>
          {chosen && (
            <span className="text-small text-secondary">
              {t('staff.correct.now', { reading: `${formatReading(cellsFromCubicMetres(chosen.last_reading))} m³` })}
            </span>
          )}
        </div>
        <div className={styles.filter}>
          <label htmlFor={readingId}>{t('staff.correct.reading')}</label>
          <input
            id={readingId}
            className={styles.search}
            inputMode="decimal"
            placeholder="355.036"
            value={reading}
            onChange={(e) => setReading(e.target.value)}
          />
        </div>
        <div className={styles.filter}>
          <label htmlFor={reasonId}>{t('staff.correct.reason')}</label>
          <input
            id={reasonId}
            className={styles.search}
            placeholder={t('staff.correct.reasonHint')}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            maxLength={200}
          />
        </div>
        <Button type="submit" variant="secondary" loading={busy}>
          {t('staff.correct.submit')}
        </Button>
      </form>
      {open.length > 0 && (
        <>
          <h3 className="panel-title">{t('staff.correct.waiting')}</h3>
          <ul className={styles.stack}>
            {open.map((row) => (
              <li key={row.id}>
                <p>
                  {t('staff.correct.request', {
                    name: row.customer_name ?? row.customer_id, meter: row.meter_id,
                    from: m3(row.current_m3), to: m3(row.reading_m3), who: row.requested_by,
                  })}
                </p>
                <p className="text-small text-secondary">{row.reason}</p>
                {row.requested_by === user?.username ? (
                  <p className="text-small text-secondary">{t('staff.correct.notYours')}</p>
                ) : declining === row.id ? (
                  <div className={styles.form}>
                    <label className={styles.filter}>
                      {t('staff.payments.reason')}
                      <input className={styles.search} maxLength={200} value={declineWhy} onChange={(e) => setDeclineWhy(e.target.value)} />
                    </label>
                    <div className={styles.rowActions}>
                      <Button variant="secondary" loading={busy} disabled={declineWhy.trim().length < 3} onClick={() => decide(row, 'decline')}>
                        {t('staff.correct.decline')}
                      </Button>
                      <Button variant="text" onClick={() => setDeclining(null)}>{t('action.cancel')}</Button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.rowActions}>
                    <Button variant="secondary" loading={busy} onClick={() => decide(row, 'approve')}>{t('staff.correct.approve')}</Button>
                    <Button variant="text" onClick={() => setDeclining(row.id)}>{t('staff.correct.decline')}</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export default MeterCorrection;
