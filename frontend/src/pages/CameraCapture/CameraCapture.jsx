/**
 * @file CameraCapture.jsx
 * @description Submit flow, step 1: photograph the meter.
 * Live camera where the phone allows it; uploading a photo or typing the
 * numbers are always offered, so a missing camera or a bad photo never
 * blocks the household. The photo is kept if sending fails.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import { errorMessage } from '../../components/RequestState/RequestState';
import { useI18n } from '../../i18n/I18nProvider';
import { useSubmission } from '../../household/submission';
import { frameToDataUrl, fileToDataUrl, dataUrlToBlob } from '../../household/photo';
import { api } from '../../api/client';
import styles from './CameraCapture.module.css';

function CameraCapture() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const submission = useSubmission();
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const fileRef = useRef(null);

  // camera: starting | live | unavailable
  const [camera, setCamera] = useState('starting');
  // send: idle | sending | failed | unreadable | saved
  // "saved": back on this screen (or reloaded) with a photo not yet read.
  const [send, setSend] = useState(submission.photo && !submission.cells ? 'saved' : 'idle');
  const [error, setError] = useState(null);

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

  const sendPhoto = async (photo) => {
    setSend('sending');
    setError(null);
    try {
      const result = await api.submitPhoto(dataUrlToBlob(photo));
      if (result.status === 'unreadable') {
        setSend('unreadable');
        return;
      }
      submission.setReadResult(result.predicted_reading, result.confidence);
      navigate('/submit/confirm');
    } catch (err) {
      setError(err);
      setSend('failed');
    }
  };

  const takePhoto = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const photo = frameToDataUrl(video);
    submission.setPhoto(photo);
    stopCamera();
    sendPhoto(photo);
  };

  const choseFile = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const photo = await fileToDataUrl(file);
      submission.setPhoto(photo);
      stopCamera();
      sendPhoto(photo);
    } catch {
      setError({ kind: 'notImage' });
      setSend('failed');
    }
  };

  const retake = () => {
    submission.reset();
    setSend('idle');
    setError(null);
  };

  const typeNumbers = () => {
    submission.startManual();
    navigate('/submit/confirm');
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
    action = (
      <>
        <Button variant="text" onClick={retake}>
          {t('camera.retake')}
        </Button>
        <Button fullWidth onClick={() => sendPhoto(submission.photo)}>
          {t('camera.sendAgain')}
        </Button>
      </>
    );
  } else if (send === 'unreadable') {
    action = (
      <>
        <Button variant="text" icon="keypad" onClick={typeNumbers}>
          {t('camera.type')}
        </Button>
        <Button fullWidth icon="camera" onClick={retake}>
          {t('camera.retake')}
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

  return (
    <Screen
      title={t('camera.title')}
      step={t('flow.step', { current: 1, total: 3 })}
      back="/home"
      action={action}
    >
      {/* Messages first: when something went wrong, that matters more than the photo. */}
      {send === 'unreadable' && (
        <Notice tone="info" live title={t('camera.unreadable.title')}>
          {t('camera.unreadable.body')}
        </Notice>
      )}

      {send === 'failed' && (
        <Notice tone="error" live>
          {error?.kind === 'notImage' ? t('camera.notImage') : errorMessage(t, error)}{' '}
          {submission.photo && t('camera.photoKept')}
        </Notice>
      )}

      {send === 'saved' && <Notice tone="info">{t('camera.saved')}</Notice>}

      {showPreview ? (
        <img className={styles.frame} src={submission.photo} alt={t('camera.photoAlt')} />
      ) : camera !== 'unavailable' && (
        <div className={styles.frame}>
          <video ref={videoRef} className={styles.video} autoPlay playsInline muted />
          {camera === 'live' && <div className={styles.guide} aria-hidden="true" />}
          {camera === 'starting' && (
            <p role="status" className={styles.overlayText}>
              {t('camera.starting')}
            </p>
          )}
        </div>
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

      {send === 'idle' && camera !== 'unavailable' && <p className="measure">{t('camera.hint')}</p>}

      {send === 'idle' && camera === 'unavailable' && (
        <Notice tone="info" title={t('camera.unavailable.title')}>
          {t('camera.unavailable.body')}
        </Notice>
      )}
    </Screen>
  );
}

export default CameraCapture;
