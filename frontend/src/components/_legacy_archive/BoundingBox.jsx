import React from 'react';
import styles from './BoundingBox.module.css';

export default function BoundingBox() {
  return (
    <div className={styles.overlay}>
      <div className={styles.box}>
        <span className={styles.corner + ' ' + styles.tl} />
        <span className={styles.corner + ' ' + styles.tr} />
        <span className={styles.corner + ' ' + styles.bl} />
        <span className={styles.corner + ' ' + styles.br} />
        <div className={styles.scanLine} />
      </div>
    </div>
  );
}
