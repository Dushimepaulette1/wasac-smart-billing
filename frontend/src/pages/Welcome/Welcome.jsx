/**
 * @file Welcome.jsx
 * @description Screen 1: Welcome and Entry Point for WASAC Smart Water Billing Platform.
 */

import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import styles from './Welcome.module.css';

export default function Welcome() {
  const navigate = useNavigate();
  const [showPinModal, setShowPinModal] = useState(false);
  const [pin, setPin] = useState(['', '', '', '']);
  const [pinError, setPinError] = useState(false);
  const inputRefs = [useRef(null), useRef(null), useRef(null), useRef(null)];

  const handlePinChange = (index, value) => {
    if (value && !/^\d$/.test(value)) return;
    const newPin = [...pin];
    newPin[index] = value;
    setPin(newPin);
    setPinError(false);

    if (value && index < 3) {
      inputRefs[index + 1].current?.focus();
    }
  };

  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !pin[index] && index > 0) {
      inputRefs[index - 1].current?.focus();
    }
  };

  const handlePinSubmit = (e) => {
    e.preventDefault();
    const enteredPin = pin.join('');
    if (enteredPin === '1234') {
      setShowPinModal(false);
      navigate('/officer');
    } else {
      setPinError(true);
      setPin(['', '', '', '']);
      inputRefs[0].current?.focus();
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.bgGradients} />
      <div className={styles.bgNoise} />
      
      <div className={styles.circleOuter} />
      <div className={styles.circleInner} />

      <div className={styles.content}>
        <div className={styles.tag}>
          <span>WASAC · Kigali</span>
        </div>

        <h1 className={styles.title}>
          Smart Water<br />Billing
        </h1>

        <p className={styles.tagline}>
          Meter reading, made simple.
        </p>

        <div className={styles.divider} />

        <div className={styles.actions}>
          <Button
            variant="primary"
            size="lg"
            fullWidth
            onClick={() => navigate('/home')}
          >
            Submit Reading
          </Button>

          <button
            type="button"
            className={styles.officerBtn}
            onClick={() => {
              setShowPinModal(true);
              setPinError(false);
              setPin(['', '', '', '']);
              setTimeout(() => inputRefs[0].current?.focus(), 150);
            }}
          >
            Officer Mode
          </button>
        </div>

        <p className={styles.footerNote}>
          Rwanda Water and Sanitation Corporation
        </p>
      </div>

      {showPinModal && (
        <div className={styles.modalOverlay} onClick={() => setShowPinModal(false)}>
          <div
            className={styles.modalCard}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="pin-modal-title"
          >
            <div className={styles.modalHeader}>
              <div className={styles.officerBadge}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 2L4 5V11.09C4 16.14 7.41 20.85 12 22C16.59 20.85 20 16.14 20 11.09V5L12 2Z"
                    stroke="var(--color-accent)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M9 12L11 14L15 10"
                    stroke="var(--color-accent)"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h2 id="pin-modal-title" className={styles.modalTitle}>Officer Access</h2>
              <p className={styles.modalSubtitle}>
                Enter your 4-digit security PIN to proceed
              </p>
            </div>

            <form onSubmit={handlePinSubmit} className={styles.pinForm}>
              <div className={styles.pinGrid}>
                {pin.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={inputRefs[idx]}
                    type="password"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handlePinChange(idx, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(idx, e)}
                    className={`${styles.pinBox} ${digit ? styles.pinFilled : ''} ${
                      pinError ? styles.pinBoxError : ''
                    }`}
                    aria-label={`Digit ${idx + 1}`}
                  />
                ))}
              </div>

              {pinError && (
                <div className={styles.errorText}>
                  Incorrect PIN. Please try again. (Default: 1234)
                </div>
              )}

              <div className={styles.modalActions}>
                <Button
                  variant="primary"
                  size="md"
                  fullWidth
                  type="submit"
                  disabled={pin.some((d) => d === '')}
                >
                  Verify and Continue
                </Button>
                <Button
                  variant="ghost"
                  size="md"
                  fullWidth
                  type="button"
                  onClick={() => setShowPinModal(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
