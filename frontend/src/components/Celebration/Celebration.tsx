/**
 * @file Celebration.tsx
 * @description The moment a bill is paid: a check that springs in, a ring that spreads, and a
 * short burst of imigongo diamonds. CSS only, decorative (the words beside it carry the
 * meaning), and still for people who ask for reduced motion.
 */

import Icon from '../Icon/Icon';
import styles from './Celebration.module.css';

const PIECES = 14;

function Celebration() {
  return (
    <div className={styles.root} aria-hidden="true">
      <span className={styles.ring} />
      {Array.from({ length: PIECES }, (_, i) => (
        <span
          key={i}
          className={styles.piece}
          style={{ ['--angle' as string]: `${(360 / PIECES) * i}deg`, ['--delay' as string]: `${(i % 4) * 40}ms` }}
        />
      ))}
      <span className={styles.badge}>
        <Icon name="check" size={44} />
      </span>
    </div>
  );
}

export default Celebration;
