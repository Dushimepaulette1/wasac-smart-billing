/**
 * @file Card.jsx
 * @description Versatile surface container with multiple visual variants.
 * Used throughout the platform for content grouping, bill summaries,
 * reading panels, and interactive list items.
 */

import React from 'react';
import styles from './Card.module.css';

/**
 * @typedef {Object} CardProps
 * @property {React.ReactNode} children - Card content
 * @property {'default'|'elevated'|'accent'|'ghost'} [variant='default'] - Visual style
 * @property {'sm'|'md'|'lg'} [padding='md'] - Internal padding preset
 * @property {Function} [onClick] - If provided, card becomes interactive
 * @property {string} [className] - Additional class names
 * @property {React.CSSProperties} [style] - Inline style override (dynamic values only)
 */

/**
 * Card component — a styled content surface container.
 */
function Card({
  children,
  variant = 'default',
  padding = 'md',
  onClick,
  className = '',
  style,
  ...rest
}) {
  const isInteractive = typeof onClick === 'function';

  const classNames = [
    styles.card,
    styles[`variant-${variant}`],
    styles[`padding-${padding}`],
    isInteractive ? styles.interactive : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  if (isInteractive) {
    return (
      <button
        type="button"
        className={classNames}
        onClick={onClick}
        style={style}
        {...rest}
      >
        {children}
      </button>
    );
  }

  return (
    <div
      className={classNames}
      style={style}
      {...rest}
    >
      {children}
    </div>
  );
}

export default Card;
