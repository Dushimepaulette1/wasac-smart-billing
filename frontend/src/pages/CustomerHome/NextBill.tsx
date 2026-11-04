/**
 * @file NextBill.tsx
 * @description "Your next bill": an estimate from the household's usual use,
 * which a number read off the meter today can sharpen. The number is not
 * saved and not billed; it only changes the estimate.
 */

import { useId, useState } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import type { UsageSummary } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres, cellsToDigits, isComplete } from '../../utils/reading';
import styles from './CustomerHome.module.css';

interface NextBillProps {
  customerId: string;
  usage: UsageSummary;
}

function NextBill({ customerId, usage }: NextBillProps) {
  const { t, rwf, volume, date } = useI18n();
  const labels = useCounterLabels();
  const helpId = useId();
  const [open, setOpen] = useState(false);
  // Starts at the last reading: the household only changes the digits that moved.
  const [cells, setCells] = useState(() => cellsFromCubicMetres(usage.last_reading_m3 ?? 0));
  const [state, setState] = useState<'idle' | 'loading' | 'failed'>('idle');
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<UsageSummary | null>(null);

  if (usage.projected_amount == null || usage.projected_m3 == null) return null;
  const shown = result ?? usage;

  const estimate = async () => {
    if (!isComplete(cells)) return;
    setState('loading');
    try {
      setResult(await api.getUsage(customerId, Number(cellsToDigits(cells)) / 1000));
      setState('idle');
    } catch (e) {
      // The typed number stays in the counter, so trying again needs no retyping.
      setError(e);
      setState('failed');
    }
  };

  const failure =
    error instanceof ApiError && error.status === 422 ? t('home.next.lower') : `${errorMessage(t, error)} ${t('home.next.kept')}`;

  return (
    <section className={`panel ${styles.nextPanel}`} aria-labelledby="next-title">
      <h2 id="next-title" className="panel-title">
        {t('home.next.title')}
      </h2>
      <p className={styles.nextAmount}>
        {t('home.next.amount', { amount: rwf(shown.projected_amount ?? 0), volume: volume(shown.projected_m3 ?? 0) })}
      </p>
      {shown.projected_on && <p className="text-small">{t('home.next.around', { date: date(shown.projected_on) })}</p>}
      <p className="text-small text-secondary">
        {t(result?.used_meter_now ? 'home.next.noteToday' : 'home.next.note')}
      </p>
      {result && !result.used_meter_now && <p className="text-small">{t('home.next.tooSoon')}</p>}

      {result?.leak_so_far && (
        <Notice tone="error" live title={t('home.next.leakSoFar')}>
          {t('home.leak.watch')}
        </Notice>
      )}

      {open ? (
        <div className={styles.nextCheck}>
          <p id={helpId} className="text-small">
            {t('home.next.checkHelp')}
          </p>
          <MeterCounter cells={cells} labels={labels} mode="edit" showValue onChange={setCells} describedBy={helpId} />
          {state === 'failed' && (
            <Notice tone="error" live>
              {failure}
            </Notice>
          )}
          <Button onClick={estimate} disabled={!isComplete(cells) || state === 'loading'}>
            {t(state === 'loading' ? 'home.next.estimating' : 'home.next.estimate')}
          </Button>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setOpen(true)}>
          {t('home.next.check')}
        </Button>
      )}
    </section>
  );
}

export default NextBill;
