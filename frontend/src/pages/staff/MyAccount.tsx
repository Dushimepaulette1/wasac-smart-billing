/**
 * @file MyAccount.tsx
 * @description The signed-in person's account: who they are, their role,
 * and changing their password (first thing to do with a temporary one).
 */

import { useId, useState, type FormEvent } from 'react';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import { errorMessage } from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { api, ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { useAuth } from '../../staff/auth';
import styles from '../../staff/staff.module.css';

const MIN_LENGTH = 10;

function MyAccount() {
  const { t } = useI18n();
  const { user, renew } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [repeat, setRepeat] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: 'error' | 'done'; text: string } | null>(null);
  const currentId = useId();
  const nextId = useId();
  const repeatId = useId();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next.length < MIN_LENGTH) return setResult({ tone: 'error', text: t('staff.password.short', { count: MIN_LENGTH }) });
    if (next !== repeat) return setResult({ tone: 'error', text: t('staff.password.mismatch') });
    setBusy(true);
    setResult(null);
    try {
      renew(await api.changePassword(current, next));
      setCurrent('');
      setNext('');
      setRepeat('');
      setResult({ tone: 'done', text: t('staff.password.changed') });
    } catch (err) {
      const wrong = err instanceof ApiError && err.kind === 'invalid';
      setResult({ tone: 'error', text: wrong ? t('staff.password.wrongCurrent') : errorMessage(t, err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <StaffLayout title={t('staff.nav.account')}>
      <div className={styles.stack}>
        {user && (
          <section className="panel" aria-label={t('staff.nav.account')}>
            <dl className={styles.facts}>
              <dt>{t('staff.accounts.name')}</dt>
              <dd>{user.full_name}</dd>
              <dt>{t('signin.username')}</dt>
              <dd className="code">{user.username}</dd>
              <dt>{t('staff.accounts.col.role')}</dt>
              <dd>
                {t(`staff.role.${user.role}`)}
                <span className={styles.cellSub}>{t(`staff.roleCan.${user.role}`)}</span>
              </dd>
            </dl>
          </section>
        )}

        <section className="panel" aria-labelledby="password-title">
          <h2 id="password-title" className="panel-title">
            {t('staff.password.title')}
          </h2>
          {user?.must_change_password && !result && (
            <Notice tone="held" title={t('staff.password.temporaryTitle')}>
              {t('staff.password.temporary')}
            </Notice>
          )}
          {result && (
            <Notice tone={result.tone} live>
              {result.text}
            </Notice>
          )}
          <form className={styles.form} onSubmit={submit} noValidate>
            <div className={styles.filter}>
              <label htmlFor={currentId}>{t('staff.password.current')}</label>
              <input id={currentId} type="password" className={styles.search} value={current}
                onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
            </div>
            <div className={styles.filter}>
              <label htmlFor={nextId}>{t('staff.password.new')}</label>
              <input id={nextId} type="password" className={styles.search} value={next}
                onChange={(e) => setNext(e.target.value)} autoComplete="new-password"
                aria-describedby={`${nextId}-hint`} />
              <span id={`${nextId}-hint`} className="text-small text-secondary">
                {t('staff.password.hint', { count: MIN_LENGTH })}
              </span>
            </div>
            <div className={styles.filter}>
              <label htmlFor={repeatId}>{t('staff.password.repeat')}</label>
              <input id={repeatId} type="password" className={styles.search} value={repeat}
                onChange={(e) => setRepeat(e.target.value)} autoComplete="new-password" />
            </div>
            <Button type="submit" loading={busy}>
              {t('staff.password.submit')}
            </Button>
          </form>
        </section>
      </div>
    </StaffLayout>
  );
}

export default MyAccount;
