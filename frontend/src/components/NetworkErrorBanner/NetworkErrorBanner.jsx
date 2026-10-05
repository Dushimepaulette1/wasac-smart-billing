/**
 * @file NetworkErrorBanner.jsx
 * @description Animated error notification banner that slides down from the top.
 * Auto-dismisses after 8 seconds with a visible countdown progress bar.
 * Provides manual dismiss and retry actions.
 */

import React, { useEffect, useRef, useState } from 'react';
import styles from './NetworkErrorBanner.module.css';

/** Duration in milliseconds before auto-dismiss */
const AUTO_DISMISS_MS = 8000;

/**
 * @typedef {Object} NetworkErrorBannerProps
 * @property {string} [message='A network error occurred. Please check your connection.'] - Error message text
 * @property {Function} [onRetry] - Called when the user clicks Retry
 * @property {Function} [onDismiss] - Called when the banner is dismissed (by user or auto)
 */

/**
 * NetworkErrorBanner component — auto-dismissing error notification.
 */
function NetworkErrorBanner({
  message = 'A network error occurred. Please check your connection.',
  onRetry,
  onDismiss,
}) {
  const [visible, setVisible] = useState(true);
  const timerRef = useRef(null);

  const dismiss = () => {
    setVisible(false);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (onDismiss) onDismiss();
  };

  const handleRetry = () => {
    dismiss();
    if (onRetry) onRetry();
  };

  useEffect(() => {
    timerRef.current = setTimeout(dismiss, AUTO_DISMISS_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!visible) return null;

  return (
    <div
      className={styles.banner}
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
    >
      <div className={styles.inner}>
        {/* Warning icon */}
        <span className={styles.icon} aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M9 2L16.5 15H1.5L9 2Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <line
              x1="9" y1="7.5" x2="9" y2="10.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <circle cx="9" cy="12.5" r="0.75" fill="currentColor" />
          </svg>
        </span>

        {/* Message */}
        <p className={styles.message}>{message}</p>

        {/* Actions */}
        <div className={styles.actions}>
          {onRetry && (
            <button
              type="button"
              className={styles.retryButton}
              onClick={handleRetry}
              aria-label="Retry the failed request"
            >
              Retry
            </button>
          )}
          <button
            type="button"
            className={styles.closeButton}
            onClick={dismiss}
            aria-label="Dismiss this error notification"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
              <line x1="2" y1="2" x2="12" y2="12" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
              <line x1="12" y1="2" x2="2" y2="12" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </div>

      {/* Auto-dismiss countdown progress bar */}
      <div className={styles.progressTrack} aria-hidden="true">
        <div
          className={styles.progressBar}
          style={{ animationDuration: `${AUTO_DISMISS_MS}ms` }}
        />
      </div>
    </div>
  );
}

export default NetworkErrorBanner;
