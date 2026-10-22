/**
 * @file SignIn.tsx
 * @description Household sign-in: the phone number registered with WASAC,
 * then the 6-digit code sent to it by SMS, then (only if that number has
 * several meters) which meter. No password to remember.
 *
 * Demo households get their code on screen while SMS is not connected.
 */

import { useEffect, useId, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { api, ApiError } from '../../api/client';
import type { CodeSent } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import { useHousehold } from '../../household/session';
import { formatRwandanPhone } from '../../utils/phone';
import styles from './SignIn.module.css';

/** Only paths inside the household app, so ?next= cannot send someone elsewhere. */
function safeNext(next: string | null): string {
  return next && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/staff') ? next : '/home';
}

function SignIn() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  // From Home's "Switch meter": show the chooser although an account is chosen.
  const switching = params.get('switch') === '1';
  const household = useHousehold();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState<CodeSent | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const phoneId = useId();
  const codeId = useId();

  // Seconds until a new code can be asked for.
  useEffect(() => {
    if (wait <= 0) return undefined;
    const timer = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(timer);
  }, [wait]);

  if (household.signedIn && household.account && !switching) return <Navigate to={next} replace />;

  const message = (err: unknown, wrongKey: string) => {
    if (err instanceof ApiError && (err.kind === 'invalid' || err.kind === 'notFound')) return t(wrongKey);
    if (err instanceof ApiError && err.kind === 'tooMany') return t('signin.household.tooMany');
    return errorMessage(t, err);
  };

  const sendCode = async (e?: FormEvent) => {
    e?.preventDefault();
    if (!phone.trim()) return setError(t('signin.household.badPhone'));
    setBusy(true);
    setError(null);
    try {
      const answer = await api.requestCode(phone);
      setSent(answer);
      setCode('');
      setWait(answer.resend_after);
    } catch (err) {
      setError(message(err, 'signin.household.badPhone'));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    if (!sent) return;
    if (code.replace(/\D/g, '').length !== 6) return setError(t('signin.household.codeLength'));
    setBusy(true);
    setError(null);
    try {
      household.start(await api.verifyCode(sent.phone, code));
      // One account: RequireHousehold lets them through; several: the chooser below shows.
    } catch (err) {
      setError(message(err, 'signin.household.wrongCode'));
      setBusy(false);
    }
  };

  // Signed in, several meters on this number: which one?
  if (household.signedIn && (!household.account || switching)) {
    return (
      <Screen title={t('signin.household.chooseTitle')} lede={<p>{t('signin.household.chooseLede')}</p>} narrow>
        <ul className={styles.accounts}>
          {household.accounts.map((a) => (
            <li key={a.customer_id}>
              <button
                type="button"
                className={`panel ${styles.account}`}
                onClick={() => {
                  household.choose(a.customer_id);
                  navigate(next, { replace: true });
                }}
              >
                <span className={styles.accountName}>{a.name}</span>
                <span className="text-small">
                  {t('home.meter')} <span className="code">{a.meter_id}</span>
                  {a.sector ? ` · ${a.sector}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Screen>
    );
  }

  if (!sent) {
    return (
      <Screen
        title={t('signin.household.title')}
        lede={<p>{t('signin.household.lede')}</p>}
        back="/"
        narrow
        action={
          <Button type="submit" form="phone-form" fullWidth loading={busy}>
            {t('signin.household.sendCode')}
          </Button>
        }
      >
        <form id="phone-form" className={`panel ${styles.form}`} onSubmit={sendCode} noValidate>
          {error && (
            <Notice tone="error" live>
              {error}
            </Notice>
          )}
          <label htmlFor={phoneId} className={styles.label}>
            {t('signin.household.phone')}
          </label>
          <input
            id={phoneId}
            className={styles.input}
            type="tel"
            inputMode="tel"
            autoComplete="tel-national"
            placeholder="078 123 4567"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            aria-describedby={`${phoneId}-hint`}
          />
          <p id={`${phoneId}-hint`} className="text-small text-secondary">
            {t('signin.household.phoneHint')}
          </p>
          {/* Wide screens only; phones use the pinned button (Screen action). */}
          <Button type="submit" fullWidth loading={busy} className={styles.wideSubmit}>
            {t('signin.household.sendCode')}
          </Button>
        </form>
        <p className={styles.staff}>
          <Link to="/staff/sign-in">{t('landing.staffLink')}</Link>
        </p>
      </Screen>
    );
  }

  return (
    <Screen
      title={t('signin.household.codeTitle')}
      lede={<p>{t('signin.household.codeLede', { phone: formatRwandanPhone(sent.phone) })}</p>}
      narrow
      action={
        <Button type="submit" form="code-form" fullWidth loading={busy}>
          {t('signin.submit')}
        </Button>
      }
    >
      <form id="code-form" className={`panel ${styles.form}`} onSubmit={verify} noValidate>
        {sent.demo_code && (
          <Notice tone="info" title={t('signin.household.demoTitle')}>
            {t('signin.household.demoBody')} <strong className={`code ${styles.demoCode}`}>{sent.demo_code}</strong>
          </Notice>
        )}
        {error && (
          <Notice tone="error" live>
            {error}
          </Notice>
        )}
        <label htmlFor={codeId} className={styles.label}>
          {t('signin.household.code')}
        </label>
        <input
          id={codeId}
          className={`${styles.input} ${styles.codeInput}`}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]*"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          autoFocus
        />
        <Button type="submit" fullWidth loading={busy} className={styles.wideSubmit}>
          {t('signin.submit')}
        </Button>
        <div className={styles.row}>
          <Button
            variant="text"
            onClick={() => {
              setSent(null);
              setError(null);
            }}
          >
            {t('signin.household.changeNumber')}
          </Button>
          <Button variant="text" onClick={() => sendCode()} disabled={wait > 0 || busy}>
            {wait > 0 ? t('signin.household.resendIn', { seconds: wait }) : t('signin.household.resend')}
          </Button>
        </div>
      </form>
    </Screen>
  );
}

export default SignIn;
