/**
 * @file InputField.jsx
 * @description Premium input component with floating label animation,
 * teal focus glow, error/hint states, and optional prefix/suffix support.
 * Built with React.forwardRef for form library compatibility.
 */

import React, { useState, useId } from 'react';
import styles from './InputField.module.css';

/**
 * @typedef {Object} InputFieldProps
 * @property {string} [label] - Floating label text
 * @property {string} [value] - Controlled value
 * @property {Function} [onChange] - Change handler
 * @property {Function} [onBlur] - Blur handler
 * @property {string} [error] - Error message (shows amber state)
 * @property {string} [hint] - Hint text below input
 * @property {string} [type='text'] - Input type
 * @property {string} [placeholder] - Placeholder (shown when no label or when focused)
 * @property {boolean} [disabled] - Disabled state
 * @property {string} [name] - Input name attribute
 * @property {string} [id] - Input id (auto-generated if omitted)
 * @property {boolean} [autoFocus] - Auto-focus on mount
 * @property {boolean} [readOnly] - Read-only state
 * @property {React.ReactNode} [suffix] - Content on right side (e.g. unit label)
 * @property {React.ReactNode} [prefix] - Content on left side (e.g. icon)
 */

const InputField = React.forwardRef(function InputField(
  {
    label,
    value,
    onChange,
    onBlur,
    error,
    hint,
    type = 'text',
    placeholder,
    disabled = false,
    name,
    id: idProp,
    autoFocus = false,
    readOnly = false,
    suffix,
    prefix,
    className = '',
    ...rest
  },
  ref
) {
  const generatedId = useId();
  const id = idProp || generatedId;
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  const [focused, setFocused] = useState(false);

  const hasValue = value !== undefined && value !== null && String(value).length > 0;
  const isFloated = focused || hasValue;

  const handleFocus = () => setFocused(true);
  const handleBlur = (e) => {
    setFocused(false);
    if (onBlur) onBlur(e);
  };

  const wrapperClasses = [
    styles.wrapper,
    focused ? styles.focused : '',
    error ? styles.hasError : '',
    disabled ? styles.disabled : '',
    readOnly ? styles.readOnly : '',
    prefix ? styles.hasPrefix : '',
    suffix ? styles.hasSuffix : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  const ariaDescribedBy = [
    error ? errorId : null,
    hint && !error ? hintId : null,
  ]
    .filter(Boolean)
    .join(' ') || undefined;

  return (
    <div className={styles.fieldRoot}>
      <div className={wrapperClasses}>
        {prefix && (
          <span className={styles.prefix} aria-hidden="true">
            {prefix}
          </span>
        )}

        <div className={styles.inputWrap}>
          {label && (
            <label
              htmlFor={id}
              className={[styles.label, isFloated ? styles.labelFloated : ''].filter(Boolean).join(' ')}
            >
              {label}
            </label>
          )}

          <input
            ref={ref}
            id={id}
            name={name}
            type={type}
            value={value}
            onChange={onChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={disabled}
            readOnly={readOnly}
            autoFocus={autoFocus}
            placeholder={isFloated ? placeholder : undefined}
            aria-invalid={!!error}
            aria-describedby={ariaDescribedBy}
            className={[styles.input, label ? styles.inputWithLabel : ''].filter(Boolean).join(' ')}
            {...rest}
          />
        </div>

        {suffix && (
          <span className={styles.suffix} aria-hidden="true">
            {suffix}
          </span>
        )}
      </div>

      {error && (
        <p id={errorId} className={styles.errorMessage} role="alert" aria-live="polite">
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            aria-hidden="true"
            className={styles.errorIcon}
          >
            <circle cx="6" cy="6" r="5.5" stroke="currentColor" />
            <line x1="6" y1="3.5" x2="6" y2="6.5" stroke="currentColor" strokeLinecap="round" />
            <circle cx="6" cy="8.5" r="0.6" fill="currentColor" />
          </svg>
          {error}
        </p>
      )}

      {hint && !error && (
        <p id={hintId} className={styles.hintMessage}>
          {hint}
        </p>
      )}
    </div>
  );
});

InputField.displayName = 'InputField';

export default InputField;
