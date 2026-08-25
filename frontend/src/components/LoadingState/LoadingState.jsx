/**
 * @file LoadingState.jsx
 * @description Loading indicator component with three wave-animated dots.
 * Supports overlay, inline, and fullscreen display modes.
 */

import React from 'react';
import styles from './LoadingState.module.css';

/**
 * @typedef {Object} LoadingStateProps
 * @property {string} [message] - Primary loading message
 * @property {string} [submessage] - Secondary/detail message
 * @property {'overlay'|'inline'|'fullscreen'} [variant='inline'] - Display mode
 */

/**
 * LoadingState component — animated dot-wave indicator with message slots.
 */
function LoadingState({
  message = 'Loading',
  submessage,
  variant = 'inline',
}) {
  const rootClass = [
    styles.root,
    styles[`variant-${variant}`],
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <div className={styles.content} role="status" aria-live="polite" aria-label={message}>
      <div className={styles.dotsWrap} aria-hidden="true">
        <span className={`${styles.dot} ${styles.dot1}`} />
        <span className={`${styles.dot} ${styles.dot2}`} />
        <span className={`${styles.dot} ${styles.dot3}`} />
      </div>
      {message && <p className={styles.message}>{message}</p>}
      {submessage && <p className={styles.submessage}>{submessage}</p>}
    </div>
  );

  if (variant === 'overlay') {
    return (
      <div className={rootClass} aria-modal="true">
        {content}
      </div>
    );
  }

  if (variant === 'fullscreen') {
    return (
      <div className={rootClass}>
        <div className={styles.fullscreenBg} aria-hidden="true" />
        {content}
      </div>
    );
  }

  return (
    <div className={rootClass}>
      {content}
    </div>
  );
}

export default LoadingState;
