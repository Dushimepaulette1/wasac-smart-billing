/**
 * @file ProgressStep.jsx
 * @description Horizontal step indicator for multi-step flows such as
 * the reading submission wizard. Shows progress segments with animated
 * transitions between steps.
 */

import React from 'react';
import styles from './ProgressStep.module.css';

/**
 * @typedef {Object} ProgressStepProps
 * @property {number} currentStep - Active step index (1-based)
 * @property {number} totalSteps - Total number of steps
 * @property {string} [label] - Current step label text
 */

/**
 * ProgressStep component — horizontal segment/dot progress indicator.
 */
function ProgressStep({ currentStep, totalSteps, label }) {
  const steps = Array.from({ length: totalSteps }, (_, i) => i + 1);

  return (
    <div className={styles.root} role="group" aria-label={`Step ${currentStep} of ${totalSteps}`}>
      <div className={styles.track} aria-hidden="true">
        {steps.map((step) => {
          const isCompleted = step < currentStep;
          const isActive = step === currentStep;

          const segmentClass = [
            styles.segment,
            isActive ? styles.segmentActive : '',
            isCompleted ? styles.segmentCompleted : '',
          ]
            .filter(Boolean)
            .join(' ');

          return (
            <div key={step} className={segmentClass}>
              {isCompleted && (
                <svg
                  className={styles.checkIcon}
                  viewBox="0 0 10 8"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M1 4L3.5 6.5L9 1"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {isActive && (
                <span className={styles.activePulse} aria-hidden="true" />
              )}
            </div>
          );
        })}
      </div>

      <div className={styles.footer} aria-live="polite">
        <span className={styles.stepCount}>
          Step {currentStep} of {totalSteps}
        </span>
        {label && (
          <>
            <span className={styles.divider} aria-hidden="true">—</span>
            <span className={styles.stepLabel}>{label}</span>
          </>
        )}
      </div>
    </div>
  );
}

export default ProgressStep;
