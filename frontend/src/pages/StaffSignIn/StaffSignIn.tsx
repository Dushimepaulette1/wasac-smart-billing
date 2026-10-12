/**
 * @file StaffSignIn.tsx
 * @description Sign-in for WASAC staff, on the same stage as the landing
 * page: serif title on the gradient, the form on a light panel.
 */

import { useEffect, useId, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import SiteHeader from '../../components/SiteHeader/SiteHeader';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import Icon from '../../components/Icon/Icon';
import { errorMessage } from '../../components/RequestState/RequestState';
import { ApiError } from '../../api/client';
import { useI18n } from '../../i18n/I18nProvider';
import { useAuth } from '../../staff/auth';
import styles from './StaffSignIn.module.css';

/** Only return to paths inside the staff area (no open redirects). */
function safeNext(next: string | null): string {
  return next && next.startsWith('/staff') && !next.startsWith('//') ? next : '/staff';
}

function StaffSignIn() {
  const { t } = useI18n();
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [missing, setMissing] = useState(false);
  const userId = useId();
  const passwordId = useId();

  useEffect(() => {
    document.title = `${t('signin.title')} | ${t('app.name')}`;
  }, [t]);

  if (user) return <Navigate to={next} replace />;

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setMissing(true);
      return;
    }
    setMissing(false);
    setBusy(true);
    setError(null);
    try {
      await signIn(username, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
      setPassword('');
      setBusy(false);
    }
  };

  const message =
    error instanceof ApiError && error.kind === 'unauthorized' ? t('signin.wrong') : error ? errorMessage(t, error) : null;

  return (
    <div className={`${styles.page} stage stage-hero`}>
      <SiteHeader links={false} />
      <main className={styles.main}>
        <div className={styles.intro}>
          <h1 className="display">{t('signin.title')}</h1>
          <p className={`${styles.lede} text-lead`}>{t('signin.lede')}</p>
        </div>

        <form className={`panel ${styles.form}`} onSubmit={submit} noValidate>
          {(message || missing) && (
            <Notice tone="error" live>
              {missing ? t('signin.missing') : message}
            </Notice>
          )}

          <div className={styles.field}>
            <label htmlFor={userId}>{t('signin.username')}</label>
            <div className={styles.inputWrap}>
              <Icon name="user" size={20} className={styles.inputIcon} />
              <input
                id={userId}
                className={styles.input}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
              />
            </div>
          </div>

          <div className={styles.field}>
            <label htmlFor={passwordId}>{t('signin.password')}</label>
            <div className={styles.inputWrap}>
              <Icon name="lock" size={20} className={styles.inputIcon} />
              <input
                id={passwordId}
                className={styles.input}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
              <button
                type="button"
                className={styles.reveal}
                onClick={() => setShowPassword((s) => !s)}
                aria-pressed={showPassword}
              >
                {showPassword ? t('signin.hide') : t('signin.show')}
              </button>
            </div>
          </div>

          <Button type="submit" fullWidth loading={busy}>
            {busy ? t('signin.busy') : t('signin.submit')}
          </Button>
          <p className="text-small text-secondary">{t('signin.help')}</p>
        </form>

        <Link to="/" className={styles.back}>
          <Icon name="back" size={18} />
          {t('signin.backHome')}
        </Link>
      </main>
    </div>
  );
}

export default StaffSignIn;
