/**
 * @file ConfirmReading.tsx
 * @description Submit flow, step 2: the household checks the numbers.
 *
 * The reading is shown on the editable meter counter, under the meter's
 * number window cut from the photo. If the digit reader returned something
 * unusable (wrong length), its raw output is shown above an empty counter so
 * nothing is hidden. When the backend was unsure (CHECK_NUMBERS) the screen
 * says "Please check the numbers."; "Confirm reading" always stays enabled.
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
import { isComplete } from '../../utils/reading';
import { api, ApiError } from '../../api/client';
import { useAccount } from '../../household/session';
import styles from './ConfirmReading.module.css';

/**
 * A translated sentence with one {name} placeholder, with the value in bold.
 * The whole sentence is one string, so translators control word order.
 */
function withBold(template: string, name: string, value: string): ReactNode {
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
  const [state, setState] = useState<'idle' | 'incomplete' | 'sending' | 'failed' | 'retake'>('idle');
  const [error, setError] = useState<unknown>(null);
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

  const confirm = async () => {
    if (!isComplete(cells)) {
      setState('incomplete');
      return;
    }
    setState('sending');
    setError(null);
    try {
      const result = await api.confirmReading({
        customerId,
        meterId,
        cells,
        evidence: submission.evidence ?? undefined,
        photoId: submission.photoId,
      });
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

  const action =
    state === 'retake' ? (
      <Button fullWidth icon="camera" onClick={retake}>
        {t('camera.retake')}
      </Button>
    ) : (
      <Button fullWidth onClick={confirm} loading={state === 'sending'}>
        {state === 'sending' ? t('confirm.sending') : t('confirm.action')}
      </Button>
    );

  return (
    <Screen
      title={manual ? t('confirm.titleManual') : t('confirm.title')}
      step={t('flow.step', { current: 2, total: 3 })}
      back="/submit/camera"
      action={action}
    >
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
          onChange={submission.setCells}
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
