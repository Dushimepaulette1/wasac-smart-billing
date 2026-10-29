/**
 * @file HouseholdForm.tsx
 * @description Staff add a household (the phone can sign in straight away)
 * or edit one: name, phone, sector, serial number. The meter number never
 * changes. The server checks every field again (backend
 * app/services/households.py); these checks only say early what to fix.
 */

import { useId, useState, type FormEvent } from 'react';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import type { CustomerInfo } from '../../api/types';
import styles from './HouseholdForm.module.css';
import staff from '../../staff/staff.module.css';

const CODE = /^[A-Z0-9][A-Z0-9/-]{2,29}$/;
const SERIAL = /^[A-Z0-9][A-Z0-9/-]{2,39}$/;

/** A Rwandan mobile number as the server accepts it: 078 123 4567, +250 78..., 78... */
export function isRwandanMobile(raw: string): boolean {
  let digits = raw.replace(/[\s\-().]/g, '').replace(/^\+/, '');
  if (!/^\d+$/.test(digits)) return false;
  if (digits.startsWith('250')) digits = digits.slice(3);
  else if (digits.startsWith('0')) digits = digits.slice(1);
  return /^7\d{8}$/.test(digits);
}

const code = (v: string) => v.replace(/\s+/g, '').toUpperCase();

interface Values {
  name: string;
  phone: string;
  meter: string;
  sector: string;
  serial: string;
  reading: string;
  customer: string;
}

/** Error codes, as the server's (staff.household.err.*). */
function check(v: Values, adding: boolean): string[] {
  const errors: string[] = [];
  const name = v.name.trim();
  if (name.length < 2 || name.length > 120) errors.push('name');
  if (!isRwandanMobile(v.phone)) errors.push('phone');
  const sector = v.sector.trim();
  if (sector.length < 2 || sector.length > 60) errors.push('sector');
  if (v.serial.trim() && !SERIAL.test(code(v.serial))) errors.push('serial');
  if (adding) {
    const meter = code(v.meter);
    if (!CODE.test(meter)) errors.push('meter');
    else if (meter.startsWith('DEMO-')) errors.push('meter_demo');
    const reading = v.reading.trim().replace(',', '.');
    if (reading && !(/^\d+(\.\d{1,3})?$/.test(reading) && Number(reading) <= 99999.999)) errors.push('reading');
    const customer = code(v.customer);
    if (customer && (!CODE.test(customer) || customer.startsWith('DEMO-'))) errors.push('customer');
  }
  return errors;
}

interface HouseholdFormProps {
  /** Edit this household; without it, add a new one. */
  household?: CustomerInfo;
  onSaved: (saved: CustomerInfo) => void;
  onCancel: () => void;
}

function HouseholdForm({ household, onSaved, onCancel }: HouseholdFormProps) {
  const { t } = useI18n();
  const adding = !household;
  const [v, setV] = useState<Values>({
    name: household?.name ?? '',
    phone: household?.phone ?? '',
    meter: household?.meter_id ?? '',
    sector: household?.sector ?? '',
    serial: household?.serial_number ?? '',
    reading: '',
    customer: '',
  });
  const [errors, setErrors] = useState<string[]>([]);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();
  const titleId = `${id}-title`;

  const set = (key: keyof Values) => (e: { target: { value: string } }) => setV({ ...v, [key]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const found = check(v, adding);
    setErrors(found);
    setFailure(null);
    if (found.length) return;
    setBusy(true);
    try {
      const saved = household
        ? await api.editHousehold(household.customer_id, {
            name: v.name.trim(), phone: v.phone, sector: v.sector.trim(), serial_number: code(v.serial) || undefined,
          })
        : await api.addHousehold({
            name: v.name.trim(),
            phone: v.phone,
            meter_id: code(v.meter),
            sector: v.sector.trim(),
            serial_number: code(v.serial) || undefined,
            first_reading: v.reading.trim().replace(',', '.') || undefined,
            customer_id: code(v.customer) || undefined,
          });
      onSaved(saved);
    } catch (err) {
      const kind = err instanceof ApiError ? err.kind : null;
      setFailure(
        kind === 'conflict' ? t('staff.household.taken') : kind === 'invalid' ? t('staff.household.invalid') : errorMessage(t, err),
      );
    } finally {
      setBusy(false);
    }
  };

  const field = (key: keyof Values, label: string, opts: { hint?: string; error?: string; optional?: boolean;
    inputMode?: 'tel' | 'decimal'; placeholder?: string; autoComplete?: string } = {}) => {
    const fieldId = `${id}-${key}`;
    const hintId = opts.hint ? `${fieldId}-hint` : undefined;
    const errorId = opts.error && errors.includes(opts.error) ? `${fieldId}-error` : undefined;
    return (
      <div className={styles.field}>
        <label htmlFor={fieldId}>
          {label}
          {opts.optional && <span className={styles.optional}> {t('staff.household.optional')}</span>}
        </label>
        <input
          id={fieldId}
          className={staff.search}
          value={v[key]}
          onChange={set(key)}
          inputMode={opts.inputMode}
          placeholder={opts.placeholder}
          autoComplete={opts.autoComplete ?? 'off'}
          spellCheck={false}
          aria-invalid={errorId ? true : undefined}
          aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
        />
        {opts.hint && (
          <span id={hintId} className={styles.hint}>
            {opts.hint}
          </span>
        )}
        {errorId && (
          <span id={errorId} className={styles.error}>
            {t(`staff.household.err.${opts.error}`)}
          </span>
        )}
      </div>
    );
  };

  return (
    <section className="panel" aria-labelledby={titleId}>
      <h2 id={titleId} className="panel-title">
        {household ? t('staff.household.editTitle', { meter: household.meter_id }) : t('staff.household.addTitle')}
      </h2>
      <p className="text-small text-secondary">{adding ? t('staff.household.addLede') : t('staff.household.editLede')}</p>
      {failure && (
        <Notice tone="error" live>
          {failure}
        </Notice>
      )}
      <form onSubmit={submit} noValidate>
        <div className={styles.grid}>
          {field('name', t('staff.household.name'), { error: 'name', autoComplete: 'off' })}
          {field('phone', t('staff.household.phone'), { error: 'phone', inputMode: 'tel', placeholder: '078 123 4567',
            hint: t('staff.household.phoneHint') })}
          {adding &&
            field('meter', t('staff.household.meter'), { error: errors.includes('meter_demo') ? 'meter_demo' : 'meter',
              placeholder: 'KGL-30001' })}
          {field('sector', t('staff.household.sector'), { error: 'sector', placeholder: 'Kacyiru' })}
          {field('serial', t('staff.household.serial'), { error: 'serial', optional: true,
            hint: t('staff.household.serialHint') })}
          {adding &&
            field('reading', t('staff.household.reading'), { error: 'reading', optional: true, inputMode: 'decimal',
              placeholder: '120.500', hint: t('staff.household.readingHint') })}
          {adding &&
            field('customer', t('staff.household.customer'), { error: 'customer', optional: true,
              hint: t('staff.household.customerHint') })}
        </div>
        <div className={styles.actions}>
          <Button type="submit" loading={busy}>
            {adding ? t('staff.household.add') : t('staff.household.save')}
          </Button>
          <Button variant="text" onClick={onCancel}>
            {t('action.cancel')}
          </Button>
        </div>
      </form>
    </section>
  );
}

export default HouseholdForm;
