/**
 * @file Progress.tsx
 * @description Something is loading: the Mubazi spinner (a turning ring around a small
 * imigongo diamond) with words saying what. Announced politely; with reduced motion the ring
 * turns slowly, and the words carry the meaning either way.
 */

import styles from './Progress.module.css';

interface ProgressProps {
  label: string;
  /** On a dark photo instead of the page. */
  overlay?: boolean;
  /** Centred in the space it is given (a page or panel loading). */
  center?: boolean;
}

/** The spinner on its own, for places that already say what is happening. */
export function Spinner({ size = 40 }: { size?: number }) {
  return (
    <span className={styles.spinner} style={{ width: size, height: size }} aria-hidden="true">
      <span className={styles.ring} />
      <span className={styles.diamond} />
    </span>
  );
}

function Progress({ label, overlay = false, center = false }: ProgressProps) {
  const classes = [styles.progress, overlay ? styles.overlay : '', center ? styles.center : ''].filter(Boolean).join(' ');
  return (
    <div className={classes} role="status" aria-live="polite">
      <Spinner />
      <span className={styles.label}>{label}</span>
    </div>
  );
}

export default Progress;
