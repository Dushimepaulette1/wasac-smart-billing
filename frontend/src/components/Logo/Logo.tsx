/**
 * @file Logo.tsx
 * @description The Mubazi mark: a deep navy tile with a geometric white "M" drawn at one even
 * stroke weight, and a sky-blue point under its centre (the needle of a meter dial). The same
 * drawing is the app icon (frontend/icons/). Decorative: the name beside it, or the link's
 * label, says what it is.
 */

import styles from './Logo.module.css';

export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <svg className={styles.mark} width={size} height={size} viewBox="0 0 40 40" aria-hidden="true" focusable="false">
      <rect width="40" height="40" rx="11" className={styles.tile} />
      <path
        d="M11.5 27V13.5l8.5 10 8.5-10V27"
        fill="none"
        className={styles.letter}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="30.2" r="1.9" className={styles.point} />
    </svg>
  );
}

export default LogoMark;
