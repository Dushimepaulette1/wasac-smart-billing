/**
 * @file Logo.tsx
 * @description The Mubazi mark: a navy square, turned 3 degrees, with a white italic serif "M".
 * Hovering the link it sits in turns it to 12 degrees. Decorative: the name beside it (or the
 * link's label) says what it is.
 */

import styles from './Logo.module.css';

export function LogoMark({ size = 36 }: { size?: number }) {
  return (
    <span className={styles.mark} style={{ width: size, height: size, fontSize: size * 0.72 }} aria-hidden="true">
      M
    </span>
  );
}

export default LogoMark;
