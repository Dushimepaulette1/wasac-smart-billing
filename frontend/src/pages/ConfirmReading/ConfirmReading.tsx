/**
 * @file ConfirmReading.tsx
 * @description Submit flow, step 2: the household checks the numbers.
 *
 * The reading is shown on the editable meter counter. If the digit reader
 * returned something unusable (wrong length), its raw output is shown
 * above an empty counter so nothing is hidden. A low-confidence read shows
 * a soft retake prompt; "Confirm reading" always stays enabled.
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
import { isComplete } from '../../utils/reading';
import { api } from '../../api/client';
import { CUSTOMER_ID, METER_ID } from '../../config';
import styles from './ConfirmReading.module.css';

/** Below this digit-reader confidence, suggest checking or retaking. */
export const LOW_CONFIDENCE = 0.8;

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
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const submission = useSubmission();
  const labels = useCounterLabels();
  const helpId = useId();
  const [state, setState] = useState<'idle' | 'incomplete' | 'sending' | 'failed' | 'retake'>('idle');
  const [error, setError] = useState<unknown>(null);
  // Set just before the submission is cleared on success, so clearing it
  // does not trigger the "no reading yet" redirect below.
  const leaving = useRef(false);

  const { cells, photo, raw, needsCheck, manual, confidence } = submission;
  const lowConfidence = !manual && !needsCheck && confidence != null && confidence < LOW_CONFIDENCE;

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
      const result = await api.confirmReading({ customerId: CUSTOMER_ID, meterId: METER_ID, cells });
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
          {errorMessage(t, error)} {t('confirm.kept')}
        </Notice>
      )}

      {state === 'retake' && (
        <Notice tone="info" live title={t('confirm.retakeTitle')}>
          {t('confirm.retakeBody')}
        </Notice>
      )}

      {photo && <img className={styles.photo} src={photo} alt={t('camera.photoAlt')} />}

      <section className={styles.reading} aria-labelledby={helpId}>
        <p id={helpId} className="measure">
          {lead}
        </p>

        <MeterCounter
          cells={cells}
          labels={labels}
          mode="edit"
          showValue
          locale={locale}
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

      {lowConfidence && state !== 'retake' && (
        <Notice
          tone="info"
          actions={
            <Button variant="text" icon="camera" onClick={retake}>
              {t('camera.retake')}
            </Button>
          }
        >
          {t('confirm.lowConfidence')}
        </Notice>
      )}
    </Screen>
  );
}

export default ConfirmReading;
