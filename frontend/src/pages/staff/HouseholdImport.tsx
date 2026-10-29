/**
 * @file HouseholdImport.tsx
 * @description Supervisors and admins upload WASAC's customer list as a CSV
 * (name, phone, meter number, sector; serial number, first reading and
 * customer number optional). The server first previews it: new, updated,
 * unchanged, and every row with a mistake. Nothing is saved until Confirm,
 * and Confirm only works when no row has a mistake.
 */

import { useId, useState, type ChangeEvent } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import type { HouseholdImportResult, HouseholdImportRow } from '../../api/types';
import styles from './HouseholdForm.module.css';
import staff from '../../staff/staff.module.css';

const MAX_BYTES = 2_000_000;
const SAMPLE =
  'name,phone,meter_number,sector,serial_number,first_reading,customer_number\n' +
  'Mukamana Alice,0788 123 456,KGL-30001,Remera,ITR24123456,120.500,\n' +
  'Habimana Eric,0722 000 444,KGL-30002,Gisozi,,,\n';
/** Rows listed in the preview: every mistake, then this many of the rest. */
const SHOWN_OK = 30;

interface HouseholdImportProps {
  onImported: () => void;
  onCancel: () => void;
}

function HouseholdImport({ onImported, onCancel }: HouseholdImportProps) {
  const { t } = useI18n();
  const [file, setFile] = useState<{ name: string; text: string } | null>(null);
  const [preview, setPreview] = useState<HouseholdImportResult | null>(null);
  const [done, setDone] = useState<HouseholdImportResult | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputId = useId();

  const send = async (text: string, apply: boolean) => {
    setBusy(true);
    setFailure(null);
    try {
      const result = await api.importHouseholds(text, apply);
      if (result.applied) {
        setDone(result);
        setPreview(null);
        setFile(null);
        onImported();
      } else {
        setPreview(result);
      }
    } catch (err) {
      setPreview(null);
      setFailure(err instanceof ApiError && err.kind === 'invalid' ? t('staff.import.badFile') : errorMessage(t, err));
    } finally {
      setBusy(false);
    }
  };

  const choose = async (e: ChangeEvent<HTMLInputElement>) => {
    const chosen = e.target.files?.[0];
    e.target.value = '';
    setDone(null);
    setPreview(null);
    if (!chosen) return;
    if (chosen.size > MAX_BYTES) {
      setFailure(t('staff.import.tooBig'));
      return;
    }
    const text = await chosen.text();
    setFile({ name: chosen.name, text });
    send(text, false);
  };

  const sampleHref = `data:text/csv;charset=utf-8,${encodeURIComponent(SAMPLE)}`;
  const problems = preview?.rows.filter((r) => r.action === 'error') ?? [];
  const others = preview?.rows.filter((r) => r.action !== 'error').slice(0, SHOWN_OK) ?? [];

  return (
    <section className="panel" aria-labelledby="import-title">
      <h2 id="import-title" className="panel-title">
        {t('staff.import.title')}
      </h2>
      <p className="text-small text-secondary">{t('staff.import.lede')}</p>

      {done && (
        <Notice tone="done" live>
          {t('staff.import.done', { added: done.new, updated: done.update })}
        </Notice>
      )}
      {failure && (
        <Notice tone="error" live>
          {failure}
        </Notice>
      )}

      <div className={styles.drop}>
        <label htmlFor={inputId} className={styles.field}>
          {t('staff.import.choose')}
        </label>
        <input id={inputId} type="file" accept=".csv,text/csv" onChange={choose} disabled={busy} />
        <span className={styles.hint}>
          {t('staff.import.columns')}{' '}
          <a href={sampleHref} download="mubazi_households_sample.csv">
            {t('staff.import.sample')}
          </a>
        </span>
      </div>

      {preview && file && (
        <>
          <h3 className={styles.field}>{t('staff.import.previewOf', { file: file.name })}</h3>
          <ul className={styles.counts} aria-live="polite">
            <li>
              {preview.new} <span>{t('staff.import.new')}</span>
            </li>
            <li>
              {preview.update} <span>{t('staff.import.update')}</span>
            </li>
            <li>
              {preview.unchanged} <span>{t('staff.import.unchanged')}</span>
            </li>
            <li className={preview.error ? styles.bad : undefined}>
              {preview.error} <span>{t('staff.import.error')}</span>
            </li>
          </ul>
          {preview.error > 0 && (
            <Notice tone="error">{t('staff.import.fixFirst', { count: preview.error })}</Notice>
          )}
          <ImportRows rows={[...problems, ...others]} />
          {preview.rows.length > problems.length + others.length && (
            <p className="text-small text-secondary">
              {t('staff.import.more', { count: preview.rows.length - problems.length - others.length })}
            </p>
          )}
        </>
      )}

      <div className={styles.actions}>
        {preview && file && (
          <Button
            loading={busy}
            disabled={preview.error > 0 || preview.new + preview.update === 0}
            onClick={() => send(file.text, true)}
          >
            {t('staff.import.confirm', { count: preview.new + preview.update })}
          </Button>
        )}
        <Button variant="text" onClick={onCancel}>
          {done ? t('staff.import.close') : t('action.cancel')}
        </Button>
      </div>
    </section>
  );
}

function ImportRows({ rows }: { rows: HouseholdImportRow[] }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  const why = (code: string) => {
    const [key, value] = code.split(':');
    return t(`staff.household.err.${key}`, { value: value ?? '' });
  };
  return (
    <div className={staff.tableWrap}>
      <table className={staff.table}>
        <thead>
          <tr>
            <th scope="col">{t('staff.import.line')}</th>
            <th scope="col">{t('staff.col.household')}</th>
            <th scope="col">{t('staff.col.meter')}</th>
            <th scope="col">{t('staff.import.result')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.line}>
              <td className="num">{r.line}</td>
              <td data-label={t('staff.col.household')}>{r.name || '–'}</td>
              <td data-label={t('staff.col.meter')} className="code">
                {r.meter_id || '–'}
              </td>
              <td data-label={t('staff.import.result')}>
                <span className={r.action === 'error' ? styles.bad : undefined}>{t(`staff.import.${r.action}One`)}</span>
                {r.action === 'update' && (
                  <span className={staff.cellSub}>{r.changes.map((c) => t(`staff.import.field.${c}`)).join(', ')}</span>
                )}
                {r.errors.map((code) => (
                  <span key={code} className={styles.rowError}>
                    {why(code)}
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default HouseholdImport;
