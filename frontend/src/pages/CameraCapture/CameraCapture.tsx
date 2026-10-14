/**
 * @file CameraCapture.tsx
 * @description Submit flow, step 1: photograph the meter.
 *
 * While the camera is open, small frames go to /guide-frame one at a time and
 * one calm tip is shown. Two good frames in a row take the photo by
 * themselves, after a short "Hold still". The shutter button always works,
 * live tips stop after 30 s, and "Save mobile data" turns them off. After the
 * photo, nothing blocks: a missing meter offers "Retake" or typing, any other
 * problem offers "Retake" or "Use this photo anyway". Uploading a photo or
 * typing the numbers is always possible, and the photo is kept if sending fails.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ChangeEvent, type RefObject } from 'react';
import { useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import Progress from '../../components/Progress/Progress';
import { errorMessage } from '../../components/RequestState/RequestState';
import { useI18n } from '../../i18n/I18nProvider';
import { useSubmission } from '../../household/submission';
import { frameToBlob, frameToDataUrl, fileToDataUrl, dataUrlToBlob } from '../../household/photo';
import { AIM_HINT, liveHint, messageKey, photoOutcome, thumbnailUrl, type PhotoOutcome } from '../../household/guidance';
import { GuidanceLoop } from '../../household/guidanceLoop';
import { useSaveData } from '../../household/saveData';
import type { PhotoSubmitResponse } from '../../api/types';
import { api } from '../../api/client';
import styles from './CameraCapture.module.css';

type CameraState = 'starting' | 'live' | 'unavailable';
/** "saved": back on this screen (or reloaded) with a photo not yet read. */
type SendState = 'idle' | 'sending' | 'failed' | 'saved' | 'outcome';
/** "ended": live tips stopped (time limit); "quiet": stopped without a message (network, no detector). */
type LiveState = 'checking' | 'ended' | 'quiet';

/** The "Hold still" moment before an automatic photo. */
export const HOLD_STILL_MS = 700;

const PHONE = '(max-width: 767px)';
const MIN_CAMERA_PX = 200;

/**
 * Phones: make the camera exactly as tall as the space between its top and the pinned buttons,
 * measured on this phone, so the tip on it is never under the buttons whatever the screen height,
 * language or message above it. Wider screens keep the CSS aspect ratio.
 */
function useFitAbovePinnedAction(ref: RefObject<HTMLDivElement>, deps: unknown[]) {
  useLayoutEffect(() => {
    const frame = ref.current;
    if (!frame || !window.matchMedia?.(PHONE).matches) return undefined;
    const fit = () => {
      const action = document.querySelector('[data-screen-action]');
      if (!action) return;
      // Leave room for what follows the camera (the "Save mobile data" switch), plus the gaps.
      const gap = parseFloat(getComputedStyle(frame.parentElement ?? frame).rowGap) || 0;
      let below = 0;
      for (let el = frame.nextElementSibling; el; el = el.nextElementSibling) {
        const height = el.getBoundingClientRect().height;
        if (height > 2) below += height + gap; // skips the visually hidden file input
      }
      const room = action.getBoundingClientRect().top - frame.getBoundingClientRect().top - below - 12;
      frame.style.height = `${Math.round(Math.max(MIN_CAMERA_PX, room))}px`;
    };
    fit();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    observer?.observe(document.body);
    window.addEventListener('resize', fit);
    return () => {
      observer?.disconnect();
      window.removeEventListener('resize', fit);
      frame.style.height = '';
    };
  }, deps); // re-measured when the layout above the camera changes
}

function CameraCapture() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const submission = useSubmission();
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<PhotoSubmitResponse | null>(null);
  const takePhotoRef = useRef<() => void>(() => undefined);
  const frameRef = useRef<HTMLDivElement>(null);

  const [camera, setCamera] = useState<CameraState>('starting');
  const [send, setSend] = useState<SendState>(submission.photo && !submission.cells ? 'saved' : 'idle');
  const [outcome, setOutcome] = useState<PhotoOutcome | null>(null);
  const [error, setError] = useState<unknown>(null);
  // The chosen file was not an image (not a network error).
  const [notImage, setNotImage] = useState(false);
  const [saveData, setSaveData] = useSaveData();
  const [live, setLive] = useState<LiveState>('checking');
  const [hint, setHint] = useState<string | null>(AIM_HINT);
  // The last answer's tip; a tip is only shown once two answers in a row agree, so it does not flicker.
  const lastTipRef = useRef<string | null>(null);

  const showPreview = submission.photo && send !== 'idle';

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    if (showPreview) return undefined;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setCamera('unavailable');
      return undefined;
    }
    setCamera('starting');
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1920 } }, audio: false })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        setCamera('live');
      })
      .catch(() => !cancelled && setCamera('unavailable'));
    return () => {
      cancelled = true;
      stopCamera();
    };
  }, [showPreview, stopCamera]);

  // Live tips: only while the camera is open, nothing is being sent, and data saving is off.
  useEffect(() => {
    if (camera !== 'live' || send !== 'idle' || saveData) return undefined;
    let holdTimer: ReturnType<typeof setTimeout> | undefined;
    setLive('checking');
    setHint(AIM_HINT);
    lastTipRef.current = null;
    const loop = new GuidanceLoop({
      grab: () => (videoRef.current ? frameToBlob(videoRef.current) : Promise.resolve(null)),
      send: (frame) => api.guideFrame(frame),
      onResult: (result) => {
        const tip = liveHint(result.guidance);
        if (tip && tip === lastTipRef.current) setHint(tip);
        lastTipRef.current = tip;
      },
      onReady: () => {
        setHint('guidance.holdStill');
        holdTimer = setTimeout(() => takePhotoRef.current(), HOLD_STILL_MS);
      },
      onEnd: (reason) => {
        setHint(null);
        setLive(reason === 'timeLimit' ? 'ended' : 'quiet');
      },
    });
    const onVisibility = () => (document.hidden ? loop.pause() : loop.resume());
    document.addEventListener('visibilitychange', onVisibility);
    loop.start();
    if (document.hidden) loop.pause();
    return () => {
      loop.stop();
      clearTimeout(holdTimer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [camera, send, saveData]);

  /** Store what the reader found and go to the confirm screen. */
  const applyResult = (result: PhotoSubmitResponse) => {
    submission.setReadResult(result.predicted_reading, result.confidence, {
      crop: thumbnailUrl(result),
      checkNumbers: result.guidance.includes('CHECK_NUMBERS') || result.needs_check,
    });
    navigate('/submit/confirm');
  };

  const sendPhoto = async (photo: string) => {
    setSend('sending');
    setError(null);
    setNotImage(false);
    setOutcome(null);
    try {
      const result = await api.submitPhoto(dataUrlToBlob(photo));
      resultRef.current = result;
      const next = photoOutcome(result);
      if (next.kind === 'confirm') {
        applyResult(result);
        return;
      }
      setOutcome(next);
      setSend('outcome');
    } catch (err) {
      setError(err);
      setSend('failed');
    }
  };

  const takePhoto = () => {
    const video = videoRef.current;
    const photo = video ? frameToDataUrl(video) : null;
    if (!photo) return;
    submission.setPhoto(photo);
    stopCamera();
    sendPhoto(photo);
  };
  takePhotoRef.current = takePhoto;

  const choseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const photo = await fileToDataUrl(file);
      submission.setPhoto(photo);
      stopCamera();
      sendPhoto(photo);
    } catch {
      setNotImage(true);
      setSend('failed');
    }
  };

  const retake = () => {
    submission.reset();
    resultRef.current = null;
    setOutcome(null);
    setSend('idle');
    setError(null);
  };

  const typeNumbers = () => {
    submission.startManual();
    navigate('/submit/confirm');
  };

  const acceptPhoto = () => {
    if (resultRef.current) applyResult(resultRef.current);
  };

  const chooseFile = () => fileRef.current?.click();

  let action;
  if (send === 'sending') {
    action = (
      <Button fullWidth loading>
        {t('camera.sending')}
      </Button>
    );
  } else if ((send === 'failed' || send === 'saved') && submission.photo) {
    const photo = submission.photo;
    action = (
      <>
        <Button variant="text" onClick={retake}>
          {t('camera.retake')}
        </Button>
        <Button fullWidth onClick={() => sendPhoto(photo)}>
          {t('camera.sendAgain')}
        </Button>
      </>
    );
  } else if (send === 'outcome' && outcome?.kind === 'soft') {
    action = (
      <>
        <Button variant="text" onClick={acceptPhoto}>
          {t('camera.useAnyway')}
        </Button>
        <Button fullWidth icon="camera" onClick={retake}>
          {t('camera.retakeShort')}
        </Button>
      </>
    );
  } else if (send === 'outcome') {
    // NO_METER, or no reading for another reason: retake or type.
    action = (
      <>
        <Button variant="text" icon="keypad" onClick={typeNumbers}>
          {t('camera.type')}
        </Button>
        <Button fullWidth icon="camera" onClick={retake}>
          {outcome?.kind === 'noMeter' ? t('camera.retakeShort') : t('camera.retake')}
        </Button>
      </>
    );
  } else if (camera === 'unavailable') {
    action = (
      <>
        <Button variant="text" icon="keypad" onClick={typeNumbers}>
          {t('camera.type')}
        </Button>
        <Button fullWidth icon="upload" onClick={chooseFile}>
          {t('camera.uploadPhoto')}
        </Button>
      </>
    );
  } else {
    action = (
      <>
        <Button variant="text" icon="upload" onClick={chooseFile}>
          {t('camera.upload')}
        </Button>
        <Button fullWidth icon="camera" onClick={takePhoto} disabled={camera !== 'live'}>
          {t('camera.take')}
        </Button>
      </>
    );
  }

  useFitAbovePinnedAction(frameRef, [camera, send, outcome, error]);

  const softKey = outcome?.kind === 'soft' ? messageKey(outcome.code) : null;
  const cameraOpen = send === 'idle' && camera !== 'unavailable';

  let liveText: string | null = null;
  if (saveData) liveText = t('camera.liveOff');
  else if (live === 'ended') liveText = t('camera.liveEnded');
  else if (hint) liveText = t(hint);

  return (
    <Screen
      title={t('camera.title')}
      step={t('flow.step', { current: 1, total: 3 })}
      back="/home"
      immersive
      action={action}
    >
      {/* Messages first: when something went wrong, that matters more than the photo. */}
      {outcome?.kind === 'noMeter' && (
        <Notice tone="info" live>
          {t('guidance.noMeter')}
        </Notice>
      )}

      {softKey && (
        <Notice tone="info" live>
          {t(softKey)}
        </Notice>
      )}

      {outcome?.kind === 'unreadable' && (
        <Notice tone="info" live title={t('camera.unreadable.title')}>
          {t('camera.unreadable.body')}
        </Notice>
      )}

      {send === 'failed' && (
        <Notice tone="error" live>
          {notImage ? t('camera.notImage') : errorMessage(t, error)}{' '}
          {submission.photo && t('camera.photoKept')}
        </Notice>
      )}

      {send === 'saved' && <Notice tone="info">{t('camera.saved')}</Notice>}

      {showPreview ? (
        <div ref={frameRef} className={styles.frame}>
          <img className={styles.video} src={submission.photo ?? undefined} alt={t('camera.photoAlt')} />
          {send === 'sending' && <Progress overlay label={t('camera.sending')} />}
        </div>
      ) : camera !== 'unavailable' && (
        <div ref={frameRef} className={styles.frame}>
          <video ref={videoRef} className={styles.video} autoPlay playsInline muted />
          {camera === 'live' && <div className={styles.guide} aria-hidden="true" />}
          {/* On the camera itself, so the tip is visible while aiming on any screen height.
              Always mounted while the camera is live, so a changed tip is announced. */}
          {camera === 'live' && send === 'idle' && (
            <p className={`panel ${styles.tip}`} role="status" aria-live="polite">
              {liveText}
            </p>
          )}
          {camera === 'starting' && (
            <p role="status" className={styles.overlayText}>
              {t('camera.starting')}
            </p>
          )}
        </div>
      )}

      {cameraOpen && camera === 'live' && (
        <>
          <label className={styles.saveData}>
            <input
              type="checkbox"
              role="switch"
              checked={saveData}
              onChange={(event) => setSaveData(event.target.checked)}
            />
            <span className={styles.saveDataLabel}>{t('camera.saveData')}</span>
          </label>
        </>
      )}

      {/* One file input for every "upload a photo" button. */}
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="visually-hidden"
        tabIndex={-1}
        aria-hidden="true"
        onChange={choseFile}
      />

      {send === 'idle' && camera === 'unavailable' && (
        <Notice tone="info" title={t('camera.unavailable.title')}>
          {t('camera.unavailable.body')}
        </Notice>
      )}
    </Screen>
  );
}

export default CameraCapture;
