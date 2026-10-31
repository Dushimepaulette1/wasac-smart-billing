/**
 * @file PaymentStatement.tsx
 * @description Supervisors and admins upload the list of payments WASAC received, as a CSV. This is
 * synthetic test data until WASAC shares real records. Once a list exists, a payment can only be
 * confirmed if its transaction ID is on it with the same amount (backend payment_statement.py).
 */

import { useId, useState, type ChangeEvent } from 'react';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import styles from '../../staff/staff.module.css';

const MAX_BYTES = 2_000_000;
const SAMPLE = 'transaction_id,amount,reference\nTEST12345,5000,KGL-20021\n';

function PaymentStatement({ onUploaded }: { onUploaded: () => void }) {
  const { t } = useI18n();
  const [result, setResult] = useState<{ tone: 'error' | 'done'; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const inputId = useId();

  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setResult({ tone: 'error', text: t('staff.import.tooBig') });
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const saved = await api.uploadPaymentStatement(await file.text());
      if (saved.errors.length) {
        setResult({ tone: 'error', text: t('staff.statement.mistakes', { lines: saved.errors.map((c) => c.split(':')[0]).join(', ') }) });
      } else {
        setResult({ tone: 'done', text: t('staff.statement.done', { added: saved.added, updated: saved.updated }) });
        onUploaded();
      }
    } catch (err) {
      setResult({ tone: 'error', text: err instanceof ApiError && err.kind === 'invalid' ? t('staff.statement.badFile') : errorMessage(t, err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="statement-title">
      <h2 id="statement-title" className="panel-title">{t('staff.statement.title')}</h2>
      <p className="text-small text-secondary">{t('staff.statement.lede')}</p>
      {result && <Notice tone={result.tone} live>{result.text}</Notice>}
      <div className={styles.filter}>
        <label htmlFor={inputId}>{t('staff.statement.choose')}</label>
        <input id={inputId} type="file" accept=".csv,text/csv" onChange={choose} disabled={busy} />
        <a className="text-small" href={`data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`} download="mubazi_payments_test_sample.csv">
          {t('staff.import.sample')}
        </a>
      </div>
    </section>
  );
}

export default PaymentStatement;
