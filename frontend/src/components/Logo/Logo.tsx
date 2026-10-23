/**
 * @file Logo.tsx
 * @description The Mubazi mark and wordmark. The mark is an imigongo zigzag that draws an "M"
 * (the cow-dung relief art of eastern Rwanda is built from zigzags and diamonds), white on Kivu
 * deep blue, with a terracotta diamond. The same drawing is the app icon (public/favicon.svg).
 */

import styles from './Logo.module.css';

export function LogoMark({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg
      className={[styles.mark, className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="48" height="48" rx="13" fill="#1E5470" />
      <path d="M10 33V17l7 9 7-11 7 11 7-9v16" fill="none" stroke="#fff" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M24 35.5l3 3-3 3-3-3z" fill="#E58A62" />
    </svg>
  );
}

/** Mark and name together. `tagline` adds the short line under the name. */
function Logo({ tagline, size = 36 }: { tagline?: string; size?: number }) {
  return (
    <span className={styles.logo}>
      <LogoMark size={size} />
      <span className={styles.words}>
        <span className={styles.name}>Mubazi</span>
        {tagline && <span className={styles.tagline}>{tagline}</span>}
      </span>
    </span>
  );
}

export default Logo;
