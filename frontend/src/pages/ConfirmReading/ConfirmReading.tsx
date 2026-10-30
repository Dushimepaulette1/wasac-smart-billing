/**
 * @file ConfirmReading.tsx
 * @description Submit flow, step 2: the household checks the numbers.
 *
 * The reading is shown on the editable meter counter, under the meter's
 * number window cut from the photo. If the digit reader returned something
 * unusable (wrong length), its raw output is shown above an empty counter so
 * nothing is hidden. When the backend was unsure (CHECK_NUMBERS) the screen
 * says "Please check the numbers."; "Confirm reading" always stays enabled.
 *
 * Check first, then choose: "Confirm reading" first asks POST /check-reading
 * (nothing is stored). A reading that would be billed is sent straight away.
 * One that would wait for an officer is explained (lower than the last
 * reading, much higher than usual, ...) with two choices: "Check the digits"
 * (back to the counter, numbers kept) or "Send for review". If the check
 * itself fails, nothing is sent: the household can try again. The backend
 * checks everything again on sending, so a changed situation is still caught.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { errorMessage } from '../../components/RequestState/RequestState';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { localDateIso } from '../../i18n/format';
import type { HeldState } from '../ReadingHeld/ReadingHeld';
import { useSubmission } from '../../household/submission';
import { refreshHouseholdFlags } from '../../household/status';
import { cellsFromCubicMetres, formatReading, isComplete } from '../../utils/reading';
import { api, ApiError } from '../../api/client';
import type { ReadingCheckResponse } from '../../api/types';
import { useAccount } from '../../household/session';
import styles from './ConfirmReading.module.css';

/**
 * A translated sentence with one {name} placeholder, with the value in bold.
 * The whole sentence is one string, so translators control word order.
 */
function withBold(template: string, name: string, value: string): ReactNode {
  if (!template.includes(`{${name}}`)) return template;
  const [before, after = ''] = template.split(`{${name}}`);
  return (
    <>
      {before}
      <strong className="num">{value}</strong>
      {after}
    </>
  );
}

function ConfirmReading() {
  const account = useAccount();
  const customerId = account.customer_id;
  const meterId = account.meter_id ?? '';
  const { t } = useI18n();
  const navigate = useNavigate();
  const submission = useSubmission();
  const labels = useCounterLabels();
  const helpId = useId();
  const [state, setState] = useState<
    'idle' | 'incomplete' | 'checking' | 'review' | 'refused' | 'checkFailed' | 'sending' | 'failed' | 'retake'
  >('idle');
  const [error, setError] = useState<unknown>(null);
  const [check, setCheck] = useState<ReadingCheckResponse | null>(null);
  // Set just before the submission is cleared on success, so clearing it
  // does not trigger the "no reading yet" redirect below.
  const leaving = useRef(false);

  const { cells, photo, raw, needsCheck, manual, crop, checkNumbers } = submission;
  const askToCheck = !manual && !needsCheck && checkNumbers;

  useEffect(() => {
    if (state === 'incomplete' && cells && isComplete(cells)) setState('idle');
  }, [cells, state]);

  if (!cells) return leaving.current ? null : <Navigate to="/submit/camera" replace />;

  const retake = () => {
    submission.reset();
    navigate('/submit/camera');
  };

  const reading = () => ({
    customerId,
    meterId,
    cells,
    evidence: submission.evidence ?? undefined,
    photoId: submission.photoId,
  });

  /** Changing a digit after a check: the explanation no longer applies. */
  const edit = (next: typeof cells) => {
    submission.setCells(next);
    if (state === 'review' || state === 'refused' || state === 'checkFailed') {
      setState('idle');
      setCheck(null);
    }
  };

  const confirm = async () => {
    if (!isComplete(cells)) {
      setState('incomplete');
      return;
    }
    setState('checking');
    setError(null);
    setCheck(null);
    let answer: ReadingCheckResponse;
    try {
      answer = await api.checkReading(reading());
    } catch (err) {
      // Never treat a failed check as "fine": nothing is sent, the numbers stay.
      setError(err);
      setState('checkFailed');
      return;
    }
    setCheck(answer);
    if (answer.refused) setState('refused');
    else if (answer.needs_review) setState('review');
    else await send();
  };

  const send = async () => {
    setState('sending');
    setError(null);
    try {
      const result = await api.confirmReading(reading());
      refreshHouseholdFlags(); // a new message or a waiting reading may follow
      if (result.bill_id) {
        leaving.current = true;
        navigate(`/bill?id=${result.bill_id}`);
        submission.reset();
      } else if (result.anomaly?.needs_retake) {
        setState('retake');
      } else {
        leaving.current = true;
        navigate('/submit/held', { state: { cells, at: localDateIso() } satisfies HeldState });
        submission.reset();
      }
    } catch (err) {
      setError(err);
      setState('failed');
    }
  };

  let lead;
  if (manual) lead = t('confirm.manual');
  else if (needsCheck) lead = raw ? withBold(t('confirm.needsCheck'), 'raw', raw) : t('confirm.needsCheckEmpty');
  else lead = t('confirm.question');

  const busy = state === 'checking' || state === 'sending';
  let action;
  if (state === 'retake') {
    action = (
      <Button fullWidth icon="camera" onClick={retake}>
        {t('camera.retake')}
      </Button>
    );
  } else if (state === 'review') {
    action = (
      <>
        <Button variant="secondary" onClick={() => { setState('idle'); setCheck(null); }}>
          {t('confirm.review.check')}
        </Button>
        <Button fullWidth onClick={send}>
          {t('confirm.review.send')}
        </Button>
      </>
    );
  } else {
    action = (
      <Button fullWidth onClick={confirm} loading={busy}>
        {state === 'checking' ? t('confirm.checking') : state === 'sending' ? t('confirm.sending')
          : state === 'checkFailed' ? t('action.retry') : t('confirm.action')}
      </Button>
    );
  }

  const previous = check?.previous_reading_m3 != null ? `${formatReading(cellsFromCubicMetres(check.previous_reading_m3))} m³` : '';

  return (
    <Screen
      title={manual ? t('confirm.titleManual') : t('confirm.title')}
      step={t('flow.step', { current: 2, total: 3 })}
      back="/submit/camera"
      action={action}
    >
      {state === 'review' && check?.reason && (
        <Notice tone="held" live title={t('confirm.review.title')}>
          {withBold(t(`confirm.review.${check.reason}`), 'previous', previous)} {t('confirm.review.choice')}
        </Notice>
      )}

      {state === 'refused' && (
        <Notice tone="info" live>
          {t(check?.refused === 'duplicate' ? 'confirm.alreadySent' : 'confirm.notNow')}
        </Notice>
      )}

      {state === 'checkFailed' && (
        <Notice tone="error" live>
          {`${errorMessage(t, error)} ${t('confirm.checkFailed')}`}
        </Notice>
      )}

      {state === 'failed' && (
        <Notice tone="error" live>
          {error instanceof ApiError && error.kind === 'conflict'
            ? t('confirm.notNow')
            : `${errorMessage(t, error)} ${t('confirm.kept')}`}
        </Notice>
      )}

      {state === 'retake' && (
        <Notice tone="info" live title={t('confirm.retakeTitle')}>
          {t('confirm.retakeBody')}
        </Notice>
      )}

      <div className={photo && !crop ? 'columns' : undefined}>
      <section className={`panel ${styles.reading}`} aria-labelledby={helpId}>
        {crop && !manual && <img className={styles.crop} src={crop} alt={t('camera.cropAlt')} />}

        <p id={helpId} className="measure">
          {lead}
        </p>

        {askToCheck && <p className={styles.check}>{t('guidance.checkNumbers')}</p>}

        <MeterCounter
          cells={cells}
          labels={labels}
          mode="edit"
          showValue
          autoFocus={manual || needsCheck}
          onChange={edit}
          describedBy={helpId}
        />

        {!manual && !needsCheck && <p className="text-small text-secondary">{t('confirm.tapHint')}</p>}

        {state === 'incomplete' && (
          <Notice tone="error" live>
            {t('confirm.incomplete')}
          </Notice>
        )}

      </section>

      {photo && !crop && (
        <figure className={styles.photoFrame}>
          <img className={styles.photo} src={photo} alt={t('camera.photoAlt')} />
          <figcaption className="text-small text-secondary">{t('camera.photoAlt')}</figcaption>
        </figure>
      )}
      </div>
    </Screen>
  );
}

export default ConfirmReading;
