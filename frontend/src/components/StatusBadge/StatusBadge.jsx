/**
 * @file StatusBadge.jsx
 * @description Pill-shaped status indicator with dot marker for billing,
 * reading, and account statuses across the WASAC platform.
 */

import React from 'react';
import styles from './StatusBadge.module.css';

/**
 * Status label map — human readable display strings.
 * @type {Record<string, string>}
 */
const STATUS_LABELS = {
  paid: 'Paid',
  unpaid: 'Unpaid',
  review: 'Under Review',
  confirmed: 'Confirmed',
  anomaly: 'Anomaly',
  pending: 'Pending',
  current: 'Current',
  outstanding: 'Outstanding',
};

/**
 * @typedef {Object} StatusBadgeProps
 * @property {'paid'|'unpaid'|'review'|'confirmed'|'anomaly'|'pending'|'current'|'outstanding'} status
 * @property {'sm'|'md'} [size='md'] - Size preset
 */

/**
 * StatusBadge component — compact pill label with a dot indicator.
 */
function StatusBadge({ status, size = 'md' }) {
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
