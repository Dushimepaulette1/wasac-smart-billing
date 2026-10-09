/**
 * @file Button.jsx
 * @description Buttons for redesign v2. The label says exactly what happens
 * ("Take photo", "Pay RWF 4,500"); nothing is appended to it.
 *
 * primary   - black, the one main action on a screen (56px tall)
 * secondary - black outline, a real alternative (48px)
 * text      - underlined text, a minor action (48px tap area)
 *
 * The old variants "ghost" and "danger" map to text and secondary so the
 * staff screens keep working until they are rebuilt.
 */

import React from 'react';
import Icon from '../Icon/Icon';
import styles from './Button.module.css';

const VARIANTS = { primary: 'primary', secondary: 'secondary', text: 'text', ghost: 'text', danger: 'secondary' };

/**
 * @typedef {Object} ButtonProps
 * @property {React.ReactNode} children
 * @property {'primary'|'secondary'|'text'} [variant='primary']
 * @property {string} [icon] - Icon name, shown before the label
 * @property {boolean} [fullWidth]
 * @property {boolean} [loading] - Busy: the label should say what is happening
 * @property {'button'|'submit'} [type='button']
 * @property {string} [href] - Render as a link that looks like a button
 */

/**
 * @param {ButtonProps & React.ButtonHTMLAttributes<HTMLButtonElement>} props
 */
function Button({
  children,
  variant = 'primary',
  icon,
  fullWidth = false,
  loading = false,
  type = 'button',
  href,
  className,
  disabled,
  ...rest
}) {
  const classes = [
    styles.button,
    styles[VARIANTS[variant] || 'primary'],
    fullWidth ? styles.fullWidth : '',
    className || '',
  ]
    .filter(Boolean)
    .join(' ');

  const content = (
    <>
      {icon && <Icon name={icon} size={22} />}
      <span>{children}</span>
    </>
  );

  if (href) {
    return (
      <a className={classes} href={href} {...rest}>
        {content}
      </a>
    );
  }

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {content}
    </button>
  );
}

export default Button;
