/**
 * @file Button.tsx
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

import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react';
import Icon, { type IconName } from '../Icon/Icon';
import styles from './Button.module.css';

type Kind = 'primary' | 'secondary' | 'text';
/** The three kinds, plus the two old names that map onto them. */
export type ButtonVariant = Kind | 'ghost' | 'danger';

const VARIANTS: Record<ButtonVariant, Kind> = {
  primary: 'primary',
  secondary: 'secondary',
  text: 'text',
  ghost: 'text',
  danger: 'secondary',
};

interface CommonProps {
  children: ReactNode;
  variant?: ButtonVariant;
  /** Icon shown before the label. */
  icon?: IconName;
  fullWidth?: boolean;
  /** Busy: the label should say what is happening. */
  loading?: boolean;
  className?: string;
}

type AsButton = CommonProps & { href?: undefined } & Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps>;
type AsLink = CommonProps & { href: string } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps>;

/** A button, or a link that looks like one when `href` is given. */
export type ButtonProps = AsButton | AsLink;

function classesFor({ variant = 'primary', fullWidth = false, className }: CommonProps): [Kind, string] {
  const kind = VARIANTS[variant];
  const classes = [styles.button, styles[kind], fullWidth ? styles.fullWidth : '', className ?? '']
    .filter(Boolean)
    .join(' ');
  return [kind, classes];
}

function Button(props: ButtonProps) {
  const [kind, classes] = classesFor(props);
  const content = (
    <>
      {props.icon && <Icon name={props.icon} size={22} />}
      <span>{props.children}</span>
    </>
  );

  if (props.href !== undefined) {
    const { children, variant, icon, fullWidth, loading, className, ...rest } = props;
    return (
      <a className={classes} data-variant={kind} {...rest}>
        {content}
      </a>
    );
  }

  const { children, variant, icon, fullWidth, loading = false, className, type = 'button', disabled, ...rest } = props;
  return (
    <button
      type={type}
      className={classes}
      data-variant={kind}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {content}
    </button>
  );
}

export default Button;
