/**
 * @file Notice.jsx
 * @description A message in the flow of a screen: what happened and what
 * to do next. Tone is always carried by an icon and words, never colour alone.
 *
 * error - something failed; says how to fix it. Black text, "!" icon.
 * held  - a reading is being checked. Brass, clock icon. Never alarming.
 * info  - advice, such as a soft retake prompt. No frame.
 * done  - something finished, such as a payment. No frame.
 */

import React from 'react';
import Icon from '../Icon/Icon';
import styles from './Notice.module.css';

const ICONS = { error: 'alert', held: 'clock', info: 'alert', done: 'check' };

/**
 * @param {{
 *   tone?: 'error'|'held'|'info'|'done',
 *   title?: React.ReactNode,
 *   children?: React.ReactNode,
 *   actions?: React.ReactNode,
 *   live?: boolean,
 *   id?: string,
 * }} props
 *   live: announce to screen readers when it appears (errors, results).
 */
function Notice({ tone = 'info', title, children, actions, live = false, id }) {
  return (
    <div
      id={id}
      className={`${styles.notice} ${styles[tone]}`}
      role={live ? (tone === 'error' ? 'alert' : 'status') : undefined}
    >
      <Icon name={ICONS[tone]} className={styles.icon} />
      <div className={styles.body}>
        {title && <p className={styles.title}>{title}</p>}
        {children && <div className={styles.text}>{children}</div>}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </div>
  );
}

export default Notice;
