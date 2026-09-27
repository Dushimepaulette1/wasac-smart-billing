import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import BoundingBox from '../components/BoundingBox';
import QualityFeedback from '../components/QualityFeedback';
import styles from './CameraScreen.module.css';

const API = 'http://localhost:8000';

export default function CameraScreen() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const navigate = useNavigate();

  const [status, setStatus] = useState('idle'); // idle | loading | error
  const [errorMsg, setErrorMsg] = useState('');
  const [cameraError, setCameraError] = useState('');

  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      setCameraError('Camera access denied. Please allow camera permission and refresh.');
    }
  }, []);

  useEffect(() => {
    startCamera();
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
  }, [startCamera]);

  const capture = async () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    setStatus('loading');
    setErrorMsg('');

    canvas.toBlob(async (blob) => {
      const form = new FormData();
      form.append('file', blob, 'meter.jpg');

      try {
        const res = await fetch(`${API}/submit-photo`, { method: 'POST', body: form });
        const data = await res.json();

        if (data.status === 'unreadable') {
          setStatus('error');
          setErrorMsg(data.guidance_message || 'Unable to read meter. Please try again.');
        } else {
          if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
          navigate('/confirm', {
            state: {
              predictedReading: data.predicted_reading,
              confidence: data.confidence,
              qualityScore: data.quality_gate_score,
            },
          });
        }
      } catch {
        setStatus('error');
        setErrorMsg('Server error. Please check your connection and try again.');
      }
    }, 'image/jpeg', 0.9);
  };

  if (cameraError) {
    return (
      <div className={styles.container}>
        <div className={styles.errorCard}>
          <span className={styles.errorIcon}>📷</span>
          <p>{cameraError}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.viewfinder}>
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={styles.video}
        />
        <BoundingBox />
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>

      {status === 'loading' ? (
        <div className={styles.loadingBar}>
          <div className="spinner" />
          <span>Analyzing your meter…</span>
        </div>
      ) : (
        <>
          <p className={styles.guide}>Frame your meter inside the box</p>
          {status === 'error' && (
            <QualityFeedback message={errorMsg} onRetry={() => setStatus('idle')} />
          )}
          <div className={styles.footer}>
            <button
              className={`btn btn-primary ${styles.captureBtn}`}
              onClick={capture}
              disabled={status === 'loading'}
            >
              📸 Capture Meter
            </button>
            <button
              className={`btn btn-ghost ${styles.officerBtn}`}
              onClick={() => navigate('/officer')}
            >
              Officer Mode
            </button>
          </div>
        </>
      )}
    </div>
  );
}
