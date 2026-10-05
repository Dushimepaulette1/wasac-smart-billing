/**
 * @file ManualEntry.jsx
 * @description Screen 6: Manual Meter Entry for customers without camera access.
 */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import ProgressStep from '../../components/ProgressStep/ProgressStep';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import LoadingState from '../../components/LoadingState/LoadingState';
import { mockCurrentCustomer } from '../../data/customers';
import { formatDate } from '../../utils/format';
import styles from './ManualEntry.module.css';

export default function ManualEntry() {
  const navigate = useNavigate();
  const customer = mockCurrentCustomer;

  const [reading, setReading] = useState('');
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const prev = customer.previousReading;

  const handleSubmit = (e) => {
    e.preventDefault();
    setError(null);

    const val = parseInt(reading, 10);
    if (isNaN(val)) {
      setError('Please enter your current meter reading');
      return;
    }

    if (val <= prev) {
      setError(
        'This reading is lower than your previous reading. Please check the number on your meter.'
      );
      return;
    }

    setIsSubmitting(true);
    setTimeout(() => {
      navigate('/bill');
    }, 1800);
  };

  return (
    <div className={styles.container}>
      {isSubmitting && (
        <LoadingState
          variant="overlay"
          message="Calculating your bill"
          submessage="Applying progressive WASAC tariff rates..."
        />
      )}

      <PageHeader
        title="Manual Entry"
        backHref="/home"
        backLabel="Home"
      />

      <div className={styles.inner}>
        <div className={styles.progressWrap}>
          <ProgressStep currentStep={1} totalSteps={4} label="Manual Entry" />
        </div>

        <form onSubmit={handleSubmit} className={styles.formStack}>
          <Card variant="ghost" padding="md" className={styles.guideCard}>
            <div className={styles.guideIcon}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="var(--color-accent)" strokeWidth="2" />
                <path d="M12 16V12" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" />
                <circle cx="12" cy="8" r="1" fill="var(--color-accent)" />
              </svg>
            </div>
            <div className={styles.guideText}>
              <p className={styles.guideMain}>
                Enter the black digits shown on your meter display, reading from left to right.
              </p>
              <p className={styles.guideSub}>
                Ignore any red digits or decimal numbers after the comma.
              </p>
            </div>
          </Card>

          <div className={styles.inputCard}>
            <label htmlFor="manual-reading-input" className={styles.inputLabel}>
              Current Meter Display (m³)
            </label>
            <div className={styles.largeInputWrap}>
              <input
                id="manual-reading-input"
                type="number"
                inputMode="numeric"
                pattern="[0-9]*"
                placeholder="0000"
                value={reading}
                onChange={(e) => {
                  setReading(e.target.value);
                  setError(null);
                }}
                className={`${styles.hugeInput} ${error ? styles.inputError : ''}`}
                autoFocus
                required
              />
              <span className={styles.inputUnit}>m³</span>
            </div>

            {error && (
              <div className={styles.inlineError} role="alert">
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <circle cx="10" cy="10" r="9" stroke="var(--color-error)" strokeWidth="2" />
                  <line x1="10" y1="6" x2="10" y2="11" stroke="var(--color-error)" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="10" cy="14" r="1" fill="var(--color-error)" />
                </svg>
                <span>{error}</span>
              </div>
            )}
          </div>

          <Card variant="accent" padding="sm" className={styles.refCard}>
            <div className={styles.refRow}>
              <div>
                <span className={styles.refLabel}>Previous Verified Reading</span>
                <div className={styles.refSub}>
                  Recorded {formatDate(customer.lastReadingDate)}
                </div>
              </div>
              <div className={styles.refValue}>{prev.toLocaleString()} m³</div>
            </div>
          </Card>

          <div className={styles.actionBlock}>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              type="submit"
              disabled={!reading || isSubmitting}
            >
              Submit Reading
            </Button>

            <div className={styles.cameraReturnLink}>
              <Link to="/submit/camera" className={styles.camLink}>
                Have a camera? Try automatic reading instead
              </Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
