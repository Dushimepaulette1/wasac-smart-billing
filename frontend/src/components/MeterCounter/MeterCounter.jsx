/**
 * @file MeterCounter.jsx
 * @description The meter counter: a reading shown the way the wall meter
 * shows it. 5 black cells for cubic metres, 3 red cells for litres, inside
 * a brass bezel. See docs/design/DESIGN_PLAN.md, section 4.
 *
 * Display mode is static. Edit mode overlays one real text input, so
 * typing, paste, voice input and screen readers all work; tapping a cell
 * moves the cursor there and typing overwrites that digit.
 */

import React, { useEffect, useId, useRef, useState } from 'react';
import {
  READING_LENGTH,
  CUBIC_METRE_DIGITS,
  normalizeReading,
  formatReading,
} from '../../utils/reading';
import styles from './MeterCounter.module.css';

/**
 * @typedef {Object} MeterCounterLabels
 * @property {string} reading - Accessible name, e.g. "Meter reading"
 * @property {string} cubicMetres - Short unit under the black cells, e.g. "m³"
 * @property {string} litres - Unit under the red cells, e.g. "litres"
 * @property {string} cubicMetresLong - Spoken unit, e.g. "cubic metres"
 */

/**
 * @typedef {Object} MeterCounterProps
 * @property {string[]} cells - 8 cells, each '0'-'9' or '' (see utils/reading)
 * @property {MeterCounterLabels} labels - Translated strings
 * @property {'display'|'edit'} [mode]
 * @property {'large'|'small'} [size] - large for households, small for staff
 * @property {(cells: string[]) => void} [onChange] - Required in edit mode
 * @property {boolean} [autoFocus] - Edit mode: focus the first blank cell on mount
 * @property {boolean} [showValue] - Show the reading as text under the counter
 * @property {string} [locale]
 * @property {string} [describedBy] - Id of help text for the input
 */

/**
 * MeterCounter component.
 * @param {MeterCounterProps} props
 */
function MeterCounter({
  cells,
  labels,
  mode = 'display',
  size = 'large',
  onChange,
  autoFocus = false,
  showValue = false,
  locale = 'en',
  describedBy,
}) {
  const isEdit = mode === 'edit';
  const inputId = useId();
  const valueId = useId();
  const inputRef = useRef(null);
  // Caret position 0..8, like a text cursor: typing writes the cell after it,
  // Backspace clears the cell before it. The highlighted cell is the one
  // that typing will write next.
  const [caret, setCaret] = useState(() => firstBlank(cells));
  const active = Math.min(caret, READING_LENGTH - 1);
  const [focused, setFocused] = useState(false);
  const [edited, setEdited] = useState(false);

  const value = formatReading(cells, locale);
  const spokenValue = value ? `${value} ${labels.cubicMetresLong}` : '';

  useEffect(() => {
    if (isEdit && autoFocus) inputRef.current?.focus();
  }, [isEdit, autoFocus]);

  // Keep the native caret at the end so Backspace always fires an input event.
  useEffect(() => {
    const el = inputRef.current;
    if (el && focused) el.setSelectionRange(el.value.length, el.value.length);
  });

  const moveCaret = (to) => setCaret(Math.max(0, Math.min(to, READING_LENGTH)));

  const commit = (next, nextCaret) => {
    setEdited(true);
    moveCaret(nextCaret);
    onChange?.(next);
  };

  // At the end of a full reading, typing replaces the last digit.
  const typeDigits = (digits) => {
    const next = [...cells];
    let i = active;
    for (const d of digits) {
      if (i >= READING_LENGTH) break;
      next[i] = d;
      i += 1;
    }
    commit(next, i);
  };

  // Clears the digit before the caret, so typing then Backspace undoes it.
  // At the very start it clears the first digit rather than doing nothing.
  const backspace = () => {
    const next = [...cells];
    const target = Math.max(caret - 1, 0);
    next[target] = '';
    commit(next, target);
  };

  // The input's value is derived from cells, so React puts it back after
  // every change; we only read what the user did from the native event.
  const handleChange = (e) => {
    const { inputType, data } = e.nativeEvent;
    if (inputType && inputType.startsWith('delete')) {
      if (inputType === 'deleteContentForward') {
        const next = [...cells];
        next[active] = '';
        commit(next, caret);
      } else {
        backspace();
      }
      return;
    }
    const digits = (data ?? '').replace(/\D/g, '');
    if (digits) typeDigits(digits);
  };

  // A pasted reading follows the same padding rule as the digit reader.
  const handlePaste = (e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text');
    const digits = text.replace(/\D/g, '');
    if (digits.length > 1) {
      const { cells: pasted, needsCheck } = normalizeReading(digits);
      if (!needsCheck) commit(pasted, READING_LENGTH);
    } else if (digits) {
      typeDigits(digits);
    }
  };

  const handleKeyDown = (e) => {
    const moves = {
      ArrowLeft: active - 1,
      ArrowRight: active + 1,
      Home: 0,
      End: READING_LENGTH,
    };
    if (e.key in moves) {
      e.preventDefault();
      moveCaret(moves[e.key]);
    }
  };

  const handleCellPointer = (index) => (e) => {
    if (!isEdit) return;
    e.preventDefault(); // keep focus on the input, don't let the cell take it
    moveCaret(index);
    inputRef.current?.focus();
  };

  const rootClass = [styles.root, styles[size], isEdit ? styles.edit : '']
    .filter(Boolean)
    .join(' ');

  const renderCell = (digit, index) => {
    const isLitre = index >= CUBIC_METRE_DIGITS;
    const cellClass = [
      styles.cell,
      isLitre ? styles.litre : styles.cubicMetre,
      digit === '' ? styles.blank : '',
      isEdit && focused && index === active ? styles.active : '',
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <span key={index} className={cellClass} onPointerDown={handleCellPointer(index)}>
        {digit !== '' && (
          <span key={edited ? digit : 'static'} className={edited ? styles.settle : undefined}>
            {digit}
          </span>
        )}
      </span>
    );
  };

  return (
    <div className={rootClass}>
      {!isEdit && !showValue && <span className="visually-hidden">{`${labels.reading}: ${spokenValue}`}</span>}

      <div className={styles.window}>
        <div className={styles.bezel} aria-hidden="true">
          <span className={styles.group}>
            {cells.slice(0, CUBIC_METRE_DIGITS).map((d, i) => renderCell(d, i))}
          </span>
          <span className={styles.group}>
            {cells.slice(CUBIC_METRE_DIGITS).map((d, i) => renderCell(d, i + CUBIC_METRE_DIGITS))}
          </span>
        </div>

        {isEdit && (
          <input
            ref={inputRef}
            id={inputId}
            className={styles.input}
            type="text"
            inputMode="numeric"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="done"
            aria-label={labels.reading}
            aria-describedby={[showValue ? valueId : null, describedBy].filter(Boolean).join(' ') || undefined}
            value={cells.join('')}
            onChange={handleChange}
            onPaste={handlePaste}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
          />
        )}
      </div>

      <div className={`${styles.units} text-small`} aria-hidden="true">
        <span>{labels.cubicMetres}</span>
        <span>{labels.litres}</span>
      </div>

      {showValue && (
        <p id={valueId} className={`${styles.value} num`}>
          <span aria-hidden="true">{value ? `${value} ${labels.cubicMetres}` : ' '}</span>
          {value && <span className="visually-hidden">{spokenValue}</span>}
        </p>
      )}
    </div>
  );
}

// Start at the first blank; on a complete reading, start at the end.
function firstBlank(cells) {
  const i = cells.indexOf('');
  return i === -1 ? cells.length : i;
}

export default MeterCounter;
