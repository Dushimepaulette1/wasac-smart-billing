/**
 * @file StatusBadge.tsx
 * @description Pill-shaped status indicator with dot marker for billing,
 * reading, and account statuses across the WASAC platform.
 */

import styles from './StatusBadge.module.css';

export type BadgeStatus =
  | 'paid'
  | 'unpaid'
  | 'review'
  | 'confirmed'
  | 'anomaly'
  | 'pending'
  | 'current'
  | 'outstanding';

/** Status label map: human readable display strings. */
const STATUS_LABELS: Record<BadgeStatus, string> = {
  paid: 'Paid',
  unpaid: 'Unpaid',
  review: 'Under Review',
  confirmed: 'Confirmed',
  anomaly: 'Anomaly',
  pending: 'Pending',
  current: 'Current',
  outstanding: 'Outstanding',
};

interface StatusBadgeProps {
  status: BadgeStatus;
  size?: 'sm' | 'md';
}

/**
 * StatusBadge component — compact pill label with a dot indicator.
 */
function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const label = STATUS_LABELS[status] || status;

  const classNames = [
    styles.badge,
    styles[`status-${status}`],
    styles[`size-${size}`],
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classNames} aria-label={`Status: ${label}`}>
      <span className={styles.dot} aria-hidden="true" />
      <span className={styles.label}>{label}</span>
    </span>
  );
}

export default StatusBadge;
