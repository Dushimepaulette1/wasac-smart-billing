/**
 * @file ConfirmReading.jsx
 * @description Screen 4: Confirm Reading with tactile meter-styled display.
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../../components/PageHeader/PageHeader';
import ProgressStep from '../../components/ProgressStep/ProgressStep';
import Card from '../../components/Card/Card';
import Button from '../../components/Button/Button';
import LoadingState from '../../components/LoadingState/LoadingState';
import { mockPredictedReading } from '../../data/readings';
import { mockCurrentCustomer } from '../../data/customers';
import { formatConsumption } from '../../utils/format';
import styles from './ConfirmReading.module.css';

export default function ConfirmReading() {
  const navigate = useNavigate();
  const customer = mockCurrentCustomer;

  const [readingValue, setReadingValue] = useState(mockPredictedReading.value.toString());
  const [isEditing, setIsEditing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [certaintyWidth, setCertaintyWidth] = useState(0);

  const prev = customer.previousReading || mockPredictedReading.previousReading;
  const currentVal = parseInt(readingValue, 10) || 0;
  const consumption = currentVal - prev;
  const isLower = currentVal < prev;

  useEffect(() => {
    const timer = setTimeout(() => {
      setCertaintyWidth(mockPredictedReading.confidence);
    }, 200);
    return () => clearTimeout(timer);
  }, []);

  const handleConfirm = () => {
    if (isLower) return;
    setIsSubmitting(true);
    setTimeout(() => {
      navigate('/bill');
    }, 2000);
  };

  return (
    <div className={styles.container}>
      {isSubmitting && (
        <LoadingState
          variant="overlay"
          message="Validating consumption"
          submessage="Checking against historical seasonal patterns..."
        />
      )}

      <PageHeader
        title="Confirm Reading"
        backHref="/submit/camera"
        backLabel="Retake"
      />

      <div className={styles.inner}>
        <div className={styles.progressWrap}>
          <ProgressStep currentStep={2} totalSteps={4} label="Confirm Reading" />
        </div>

        <div className={styles.contentStack}>
          <div className={styles.meterDisplayCard}>
            <div className={styles.displayHeader}>
              <span className={styles.displayLabel}>Detected Reading</span>
              <button
                type="button"
                className={styles.toggleEditBtn}
                onClick={() => setIsEditing(!isEditing)}
              >
                {isEditing ? 'Done' : 'Edit reading'}
              </button>
            </div>

            {isEditing ? (
              <div className={styles.editModeWrap}>
                <input
                  type="number"
                  inputMode="numeric"
                  value={readingValue}
                  onChange={(e) => setReadingValue(e.target.value)}
                  className={styles.editableInput}
                  autoFocus
                />
                <span className={styles.m3Suffix}>m³</span>
              </div>
            ) : (
              <div className={styles.meterGlassDisplay}>
                <div className={styles.digitsRow}>
                  {readingValue.split('').map((char, i) => (
                    <span key={i} className={styles.meterChar}>
                      {char}
                    </span>
                  ))}
                </div>
                <span className={styles.meterUnitText}>CUBIC METRES (m³)</span>
              </div>
            )}

            <div className={styles.meterAccountFooter}>
              <span>Meter ID: {customer.meterID}</span>
              <span>Account: {customer.accountNumber}</span>
            </div>
          </div>

          <div className={styles.certaintyBox}>
            <div className={styles.certaintyHeader}>
              <span className={styles.certaintyLabel}>Reading certainty</span>
              <span className={styles.certaintyValue}>
                {mockPredictedReading.confidence}% · High
              </span>
            </div>
            <div className={styles.certaintyTrack}>
              <div
                className={styles.certaintyBar}
                style={{ width: `${certaintyWidth}%` }}
              />
            </div>
          </div>

          <Card variant="accent" padding="md" className={styles.deltaCard}>
            <div className={styles.deltaGrid}>
              <div className={styles.deltaItem}>
                <span className={styles.deltaLabel}>Previous Reading</span>
                <span className={styles.deltaNumber}>{prev.toLocaleString()} m³</span>
              </div>

              <div className={styles.deltaDivider} />

              <div className={styles.deltaItem}>
                <span className={styles.deltaLabel}>Current Reading</span>
                <span className={`${styles.deltaNumber} ${styles.currentNumber}`}>
                  {currentVal.toLocaleString()} m³
                </span>
              </div>

              <div className={styles.deltaDivider} />

              <div className={styles.deltaItem}>
                <span className={styles.deltaLabel}>New Consumption</span>
                <span className={`${styles.deltaNumber} ${styles.highlightDelta}`}>
                  {isLower ? '—' : formatConsumption(consumption)}
                </span>
              </div>
            </div>

            {isLower && (
              <div className={styles.errorNotice}>
                This reading is lower than your previous reading ({prev.toLocaleString()} m³). Please edit the number to match your physical meter.
              </div>
            )}
          </Card>

          <div className={styles.actionButtons}>
            <Button
              variant="primary"
              size="lg"
              fullWidth
              onClick={handleConfirm}
              disabled={isLower || !readingValue}
            >
              Confirm and Submit
            </Button>
            <Button
              variant="secondary"
              size="md"
              fullWidth
              onClick={() => setIsEditing(!isEditing)}
            >
              {isEditing ? 'Save Edits' : 'Edit Reading'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
