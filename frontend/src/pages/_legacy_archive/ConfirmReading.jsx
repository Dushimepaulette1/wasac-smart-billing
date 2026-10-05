import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import styles from './ConfirmReading.module.css';

const API = 'http://localhost:8000';
const DEMO_CUSTOMER_ID = 'CUST001';
const DEMO_METER_ID = 'MTR001';

export default function ConfirmReading() {
  const navigate = useNavigate();
  const { state } = useLocation();

  const predicted = state?.predictedReading ?? '00444';
  const confidence = state?.confidence ?? 0.88;
  const qualityScore = state?.qualityScore ?? 0.92;

  const [reading, setReading] = useState(predicted);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!reading.trim()) {
      setError('Please enter the meter reading.');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const res = await fetch(`${API}/confirm-reading`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: DEMO_CUSTOMER_ID,
          meter_id: DEMO_METER_ID,
          confirmed_reading: reading,
        }),
      });
      const data = await res.json();

      if (!data.success) {
        setError(data.error_message || 'Reading could not be validated.');
        setLoading(false);
        return;
      }

      navigate('/bill', { state: { bill: data } });
    } catch {
      setError('Could not reach the server. Please check your connection.');
      setLoading(false);
    }
  };

  const confPct = Math.round(confidence * 100);

  return (
    <div className={styles.container}>
      <div className={styles.section}>
        <h2 className={styles.title}>Confirm Your Reading</h2>
        <p className={styles.subtitle}>
          Please check this reading matches your meter display
        </p>
      </div>

      <div className={styles.readingCard}>
        <label className={styles.readingLabel}>Meter Reading (m³)</label>
        <input
          className={styles.readingInput}
          type="number"
          value={reading}
          onChange={e => setReading(e.target.value)}
          placeholder="e.g. 00444"
          inputMode="numeric"
        />
        <div className={styles.confidenceRow}>
          <span className={styles.confLabel}>AI Confidence</span>
          <span
            className={`${styles.confValue} ${confPct >= 80 ? styles.high : styles.low}`}
          >
            {confPct}%
          </span>
        </div>
        <div className={styles.confidenceBar}>
          <div
            className={styles.confidenceFill}
            style={{ width: `${confPct}%`, background: confPct >= 80 ? 'var(--green)' : 'var(--yellow)' }}
          />
        </div>
        <p className={styles.qualityNote}>
          Image quality score: {Math.round(qualityScore * 100)}%
        </p>
      </div>

      {error && (
        <div className={styles.errorBox}>
          <span>⚠️</span> {error}
        </div>
      )}

      <div className={styles.footer}>
        {loading ? (
          <div className="spinner-wrap">
            <div className="spinner" />
            <span>Validating reading…</span>
          </div>
        ) : (
          <>
            <button className="btn btn-primary" onClick={handleSubmit}>
              ✓ Confirm &amp; Submit
            </button>
            <button className="btn btn-ghost" onClick={() => navigate('/camera')}>
              ← Retake Photo
            </button>
          </>
        )}
      </div>
    </div>
  );
}
