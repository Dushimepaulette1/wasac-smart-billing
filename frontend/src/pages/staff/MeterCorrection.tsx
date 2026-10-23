/**
 * @file MeterCorrection.tsx
 * @description Supervisors and admins: set a meter's current reading when the
 * record is wrong (a replaced meter, or wrong data). The next household
 * reading is compared with it; the change is logged in Activity with the
 * reason (backend app/services/meter_correction.py).
 */

import { useId, useState, type FormEvent } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import type { HouseholdRow } from '../../staff/loadOverview';
import styles from '../../staff/staff.module.css';

interface MeterCorrectionProps {
  households: HouseholdRow[];
  onCorrected: () => void;
}

function MeterCorrection({ households, onCorrected }: MeterCorrectionProps) {
  const { t } = useI18n();
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
        text: t('staff.correct.done', {
          meter: updated.meter_id,
          reading: `${formatReading(cellsFromCubicMetres(updated.last_reading))} m³`,
        }),
      });
      setReading('');
      setReason('');
      onCorrected();
    } catch (err) {
      const pending = err instanceof ApiError && err.kind === 'conflict';
      setResult({ tone: 'error', text: pending ? t('staff.correct.pending') : errorMessage(t, err) });
    } finally {
      setBusy(false);
    }
  };

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
    </section>
  );
}

export default MeterCorrection;
