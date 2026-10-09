/**
 * @file Card.tsx
 * @description Versatile surface container with multiple visual variants.
 * Used throughout the platform for content grouping, bill summaries,
 * reading panels, and interactive list items.
 */

import type { CSSProperties, HTMLAttributes, MouseEventHandler, ReactNode } from 'react';
import styles from './Card.module.css';

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'onClick' | 'style'> {
  children: ReactNode;
  variant?: 'default' | 'elevated' | 'accent' | 'ghost';
  padding?: 'sm' | 'md' | 'lg';
  /** If provided, the card becomes a button. */
  onClick?: MouseEventHandler<HTMLElement>;
  className?: string;
  /** Inline style override (dynamic values only). */
  style?: CSSProperties;
}

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
}: CardProps) {
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
