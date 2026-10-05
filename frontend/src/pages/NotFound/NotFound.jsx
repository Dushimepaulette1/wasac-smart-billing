/**
 * @file NotFound.jsx
 * @description Screen 11: Clean, on-brand 404 page for the WASAC platform.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../../components/Button/Button';
import styles from './NotFound.module.css';

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <div className={styles.container}>
      <div className={styles.inner}>
        <div className={styles.iconCircle}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="10" stroke="var(--color-accent)" strokeWidth="1.5" />
            <polygon
              points="12,7 15,12 12,17 9,12"
              fill="var(--color-accent-light)"
              stroke="var(--color-accent)"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle cx="12" cy="12" r="1.5" fill="var(--color-accent)" />
          </svg>
        </div>

        <h1 className={styles.title}>Page not found</h1>

        <p className={styles.description}>
          The page you requested does not exist or has been relocated within the WASAC Smart Billing Platform.
        </p>

        <div className={styles.actions}>
          <Button
            variant="primary"
            size="md"
            onClick={() => navigate('/home')}
          >
            Return to Dashboard
          </Button>

          <Button
            variant="ghost"
            size="md"
            onClick={() => navigate(-1)}
          >
            Go Back
          </Button>
        </div>
      </div>
    </div>
  );
}
