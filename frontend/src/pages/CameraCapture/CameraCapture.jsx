/**
 * @file CameraCapture.jsx
 * @description Screen 3: Camera Capture with simulated AI meter detection.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import ProgressStep from '../../components/ProgressStep/ProgressStep';
import LoadingState from '../../components/LoadingState/LoadingState';
import styles from './CameraCapture.module.css';

export default function CameraCapture() {
  const navigate = useNavigate();
  const [phase, setPhase] = useState('idle');
  const [statusMessage, setStatusMessage] = useState('Hold steady — align the meter display with the frame');
  const [shutterActive, setShutterActive] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setPhase((curr) => {
        if (curr === 'idle') {
          setStatusMessage('Ready to capture — press the button below');
          return 'ready';
        }
        return curr;
      });
    }, 2000);
    return () => clearTimeout(timer);
  }, []);

  const handleCapture = () => {
    if (phase === 'captured' || phase === 'analyzing') return;

    setShutterActive(true);
    setPhase('captured');
    setStatusMessage('Reading captured');

    setTimeout(() => {
      setShutterActive(false);
      setPhase('analyzing');
      setStatusMessage('Analysing your meter display...');
    }, 350);

    setTimeout(() => {
      navigate('/submit/confirm');
    }, 2400);
  };

  return (
    <div className={styles.screenContainer}>
      <div className={styles.topBar}>
        <div className={styles.progressWrap}>
          <ProgressStep currentStep={1} totalSteps={4} label="Capture Reading" />
        </div>
      </div>

      <div className={styles.viewfinder}>
        <div className={styles.cameraFeedOverlay} />
        
        <div
          className={`${styles.boundingBox} ${
            phase === 'ready' || phase === 'captured' || phase === 'analyzing'
              ? styles.boundingReady
              : styles.boundingIdle
          }`}
        >
          <span className={`${styles.corner} ${styles.cornerTL}`} />
          <span className={`${styles.corner} ${styles.cornerTR}`} />
          <span className={`${styles.corner} ${styles.cornerBL}`} />
          <span className={`${styles.corner} ${styles.cornerBR}`} />

          <div className={`${styles.meterFace} ${phase === 'captured' ? styles.meterFrozen : ''}`}>
            <div className={styles.meterDisplayGlass}>
              <div className={styles.meterDigits}>
                <span className={styles.digit}>2</span>
                <span className={styles.digit}>8</span>
                <span className={styles.digit}>4</span>
                <span className={styles.digit}>7</span>
                <span className={`${styles.digit} ${styles.subDigit}`}>4</span>
              </div>
              <span className={styles.meterUnit}>M³ · CLASS B</span>
            </div>
            <div className={styles.meterSerial}>SER: 2021-WASAC-0941</div>
          </div>
        </div>

        <div className={styles.statusPill}>
          <span
            className={`${styles.statusDot} ${
              phase === 'ready' ? styles.dotReady : ''
            }`}
          />
          <span className={styles.statusText} key={statusMessage}>
            {statusMessage}
          </span>
        </div>
      </div>

      <div className={styles.controlsZone}>
        {phase === 'analyzing' ? (
          <div className={styles.analyzingWrapper}>
            <LoadingState
              variant="inline"
              message="Analysing meter reading"
              submessage="Verifying digit clarity and timestamp"
            />
          </div>
        ) : (
          <div className={styles.shutterRow}>
            <button
              type="button"
              className={`${styles.shutterBtn} ${
                shutterActive ? styles.shutterClicked : ''
              } ${phase === 'ready' ? styles.shutterReady : ''}`}
              onClick={handleCapture}
              disabled={phase === 'captured'}
              aria-label="Capture meter reading photo"
            >
              <span className={styles.shutterInner} />
            </button>
          </div>
        )}

        <div className={styles.manualFallback}>
          <Link to="/submit/manual" className={styles.manualLink}>
            No camera? Enter reading manually
          </Link>
        </div>
      </div>
    </div>
  );
}
