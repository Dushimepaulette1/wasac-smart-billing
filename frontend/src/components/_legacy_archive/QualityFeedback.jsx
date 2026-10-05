import React from 'react';
import styles from './QualityFeedback.module.css';

const TIPS = [
  'Hold your phone steady',
  'Clean the meter glass',
  'Move closer (30-50 cm)',
  'Ensure good lighting',
];

export default function QualityFeedback({ message, onRetry }) {
  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.icon}>⚠️</span>
        <span className={styles.title}>Unable to Read Meter</span>
      </div>
      <p className={styles.message}>{message}</p>
      <ul className={styles.tips}>
        {TIPS.map(tip => (
          <li key={tip}><span className={styles.check}>✓</span> {tip}</li>
        ))}
      </ul>
      {onRetry && (
        <button className={`btn btn-outline ${styles.retryBtn}`} onClick={onRetry}>
          Try Again
        </button>
      )}
    </div>
  );
}
