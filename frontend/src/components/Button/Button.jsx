/**
 * @file Button.jsx
 * @description Premium button component for the WASAC Smart Billing Platform.
 * Supports multiple variants (primary, secondary, ghost, danger), sizes,
 * loading state with CSS spinner, ripple effect on click, and full
 * accessibility support via React.forwardRef.
 */

import React, { useRef, useCallback } from 'react';
import styles from './Button.module.css';

/**
 * @typedef {Object} ButtonProps
 * @property {React.ReactNode} children - Button label content
 * @property {'primary'|'secondary'|'ghost'|'danger'} [variant='primary'] - Visual style
 * @property {'sm'|'md'|'lg'} [size='md'] - Size preset
 * @property {Function} [onClick] - Click handler
 * @property {boolean} [disabled] - Disabled state
 * @property {boolean} [loading] - Loading state — shows spinner, disables interaction
 * @property {boolean} [fullWidth] - Whether to fill container width
 * @property {'button'|'submit'|'reset'} [type='button'] - HTML button type
 * @property {string} [className] - Additional class names
 */

/**
 * Creates a CSS ripple effect at the click position.
 * @param {MouseEvent} event
 * @param {HTMLButtonElement} button
 */
function createRipple(event, button) {
  const existingRipple = button.querySelector(`.${styles.ripple}`);
  if (existingRipple) existingRipple.remove();

  const rect = button.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height) * 2;
  const x = event.clientX - rect.left - size / 2;
  const y = event.clientY - rect.top - size / 2;

  const ripple = document.createElement('span');
  ripple.className = styles.ripple;
  ripple.style.width = `${size}px`;
  ripple.style.height = `${size}px`;
  ripple.style.left = `${x}px`;
  ripple.style.top = `${y}px`;

  button.appendChild(ripple);

  ripple.addEventListener('animationend', () => {
    ripple.remove();
  });
}

const Button = React.forwardRef(function Button(
  {
    children,
    variant = 'primary',
    size = 'md',
    onClick,
    disabled = false,
    loading = false,
    fullWidth = false,
    type = 'button',
    className = '',
    ...rest
  },
  ref
) {
  const buttonRef = useRef(null);
  const resolvedRef = ref || buttonRef;

  const handleClick = useCallback(
    (event) => {
      if (disabled || loading) return;

      const btn = resolvedRef.current;
      if (btn && variant === 'primary') {
        createRipple(event, btn);
      }

      if (onClick) onClick(event);
    },
    [disabled, loading, onClick, resolvedRef, variant]
  );

  const classNames = [
    styles.button,
    styles[`variant-${variant}`],
    styles[`size-${size}`],
    fullWidth ? styles.fullWidth : '',
    loading ? styles.loading : '',
    disabled ? styles.disabled : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      ref={resolvedRef}
      type={type}
      className={classNames}
      onClick={handleClick}
      disabled={disabled || loading}
      aria-disabled={disabled || loading}
      aria-busy={loading}
      {...rest}
    >
      {loading && (
        <span className={styles.spinnerWrap} aria-hidden="true">
          <span className={styles.spinner} />
        </span>
      )}
      <span className={loading ? styles.labelHidden : styles.label}>
        {children}
      </span>
    </button>
  );
});

Button.displayName = 'Button';

export default Button;
