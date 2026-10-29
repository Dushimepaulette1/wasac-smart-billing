/**
 * @file Activity.tsx
 * @description The audit log: sign-ins, review decisions and account
 * changes, newest first. Officers see their own; supervisors and admins see
 * everyone's and can narrow it to one person.
 */

import { useId, useState, type FormEvent } from 'react';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import { hasRole, useAuth } from '../../staff/auth';
import { dateTime } from '../../staff/time';
import type { AnomalyType, StaffAction } from '../../api/types';
import { ISSUE_KEY } from '../../staff/issues';
import styles from '../../staff/staff.module.css';

/** Filter choices: '' is everything. */
const KINDS = ['', 'sign_in', 'sign_in_failed', 'accept', 'reject', 'close', 'account_created', 'account_updated', 'password_reset', 'password_changed', 'meter_corrected', 'payment_confirmed', 'payment_declined', 'household_added', 'household_updated', 'households_imported'] as const;

/** Actions worth a second look get the held (brass) colour. */
const WATCH = new Set(['sign_in_failed', 'password_reset', 'account_updated', 'meter_corrected', 'payment_declined', 'household_updated']);

function Activity() {
  const { t } = useI18n();
  const { user } = useAuth();
  const everyone = hasRole(user, 'supervisor');
  const [kind, setKind] = useState('');
  const [person, setPerson] = useState('');
  const rows = useRequest((filters: { username?: string; action?: string }) => api.activity(filters), {
    immediate: true,
    args: [{}],
  });
  const kindId = useId();
  const personId = useId();

  const apply = (e?: FormEvent) => {
    e?.preventDefault();
    rows.run({ action: kind || undefined, username: everyone ? person.trim() || undefined : undefined });
  };

  /** A decision's details are "<meter> <ANOMALY_TYPE>": say the type in plain words. */
  const details = (a: StaffAction) => {
    const match = /^(\S+) ([A-Z_]+)$/.exec(a.detail ?? '');
    const issue = match ? ISSUE_KEY[match[2] as AnomalyType] : undefined;
    const detail = match && issue ? `${match[1]} · ${t(issue)}` : a.detail;
    return [a.target, detail].filter(Boolean).join(' · ') || '–';
  };

  const label = (a: StaffAction) => {
    const key = `staff.activity.kind.${a.action}`;
    const text = t(key);
    return text === key ? a.action : text;
  };

  return (
    <StaffLayout title={t('staff.nav.activity')} lede={everyone ? t('staff.activity.ledeAll') : t('staff.activity.ledeOwn')}>
      <section className="panel" aria-label={t('staff.nav.activity')}>
        <form className={styles.filters} onSubmit={apply}>
          <div className={styles.filter}>
            <label htmlFor={kindId}>{t('staff.activity.what')}</label>
            <select id={kindId} className={styles.select} value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k ? t(`staff.activity.kind.${k}`) : t('staff.activity.all')}
                </option>
              ))}
            </select>
          </div>
          {everyone && (
            <div className={styles.filter}>
              <label htmlFor={personId}>{t('staff.activity.who')}</label>
              <input
                id={personId}
                className={styles.search}
                value={person}
                onChange={(e) => setPerson(e.target.value)}
                placeholder={t('staff.activity.whoHint')}
                autoCapitalize="none"
                spellCheck={false}
              />
            </div>
          )}
          <Button type="submit" variant="secondary" loading={rows.status === 'loading'}>
            {t('staff.activity.show')}
          </Button>
        </form>

        {rows.status === 'success' ? (
          rows.data.length === 0 ? (
            <p className={styles.empty}>{t('staff.activity.none')}</p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">{t('staff.activity.col.when')}</th>
                    <th scope="col">{t('staff.activity.col.who')}</th>
                    <th scope="col">{t('staff.activity.col.what')}</th>
                    <th scope="col">{t('staff.activity.col.detail')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.data.map((a) => (
                    <tr key={a.id}>
                      <td className="code">{dateTime(a.at)}</td>
                      <td data-label={t('staff.activity.col.who')}>{a.username}</td>
                      <td data-label={t('staff.activity.col.what')}>
                        <span className={WATCH.has(a.action) ? styles.flagged : undefined}>{label(a)}</span>
                      </td>
                      <td data-label={t('staff.activity.col.detail')} className="code">
                        {details(a)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <RequestState status={rows.status} error={rows.error} onRetry={rows.retry} />
        )}
      </section>
    </StaffLayout>
  );
}

export default Activity;
