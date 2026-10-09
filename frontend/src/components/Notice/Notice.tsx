/**
 * @file Notice.tsx
 * @description A message in the flow of a screen: what happened and what
 * to do next. Tone is always carried by an icon and words, never colour alone.
 *
 * error - something failed; says how to fix it. Black text, "!" icon.
 * held  - a reading is being checked. Brass, clock icon. Never alarming.
 * info  - advice, such as a soft retake prompt. No frame.
 * done  - something finished, such as a payment. No frame.
 */

import type { ReactNode } from 'react';
import Icon, { type IconName } from '../Icon/Icon';
import styles from './Notice.module.css';

export type NoticeTone = 'error' | 'held' | 'info' | 'done';

const ICONS: Record<NoticeTone, IconName> = { error: 'alert', held: 'clock', info: 'alert', done: 'check' };

interface NoticeProps {
  tone?: NoticeTone;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  /** Announce to screen readers when it appears (errors, results). */
  live?: boolean;
  id?: string;
}

function Notice({ tone = 'info', title, children, actions, live = false, id }: NoticeProps) {
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
