/**
 * @file Progress.tsx
 * @description Something is loading: a slim bar sliding along a track, with
 * words saying what. Announced politely; the bar stops moving for people who
 * ask for reduced motion, and the words carry the meaning either way.
 */

import styles from './Progress.module.css';

interface ProgressProps {
  label: string;
  /** On a dark photo instead of the page. */
  overlay?: boolean;
}

function Progress({ label, overlay = false }: ProgressProps) {
  return (
    <div className={`${styles.progress} ${overlay ? styles.overlay : ''}`} role="status" aria-live="polite">
      <span className={styles.track} aria-hidden="true">
        <span className={styles.bar} />
      </span>
      <span className={styles.label}>{label}</span>
    </div>
  );
}

export default Progress;
