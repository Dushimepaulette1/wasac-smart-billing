/**
 * @file MeterCounter.tsx
 * @description The meter counter: a reading shown the way the wall meter
 * shows it. 5 black cells for cubic metres, 3 red cells for litres, inside
 * a brass bezel. See docs/design/DESIGN_PLAN.md, section 4.
 *
 * Display mode is static. Edit mode overlays one real text input, so
 * typing, paste, voice input and screen readers all work; tapping a cell
 * moves the cursor there and typing overwrites that digit.
 */

import {
  useEffect,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type KeyboardEvent,
  type PointerEvent,
} from 'react';
import {
  READING_LENGTH,
  CUBIC_METRE_DIGITS,
  normalizeReading,
  formatReading,
  type Cells,
} from '../../utils/reading';
import styles from './MeterCounter.module.css';

export interface MeterCounterLabels {
  /** Accessible name, e.g. "Meter reading". */
  reading: string;
  /** Short unit under the black cells, e.g. "m³". */
  cubicMetres: string;
  /** Unit under the red cells, e.g. "litres". */
  litres: string;
  /** Spoken unit, e.g. "cubic metres". */
  cubicMetresLong: string;
}

export interface MeterCounterProps {
  /** 8 cells, each "0"-"9" or "" (see utils/reading). */
  cells: Cells;
  labels: MeterCounterLabels;
  mode?: 'display' | 'edit';
  /** large for households, small for staff. */
  size?: 'large' | 'small';
  /** Required in edit mode. */
  onChange?: (cells: Cells) => void;
  /** Edit mode: focus the first blank cell on mount. */
  autoFocus?: boolean;
  /** Show the reading as text under the counter. */
  showValue?: boolean;
  locale?: string;
  /** Id of help text for the input. */
  describedBy?: string;
}

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
}: MeterCounterProps) {
  const isEdit = mode === 'edit';
  const inputId = useId();
  const valueId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
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

  const moveCaret = (to: number) => setCaret(Math.max(0, Math.min(to, READING_LENGTH)));

  const commit = (next: Cells, nextCaret: number) => {
    setEdited(true);
    moveCaret(nextCaret);
    onChange?.(next);
  };

  // At the end of a full reading, typing replaces the last digit.
  const typeDigits = (digits: string) => {
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
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    // Typing produces an InputEvent; read its fields without assuming one,
    // since other sources (and tests) fire plain events.
    const { inputType, data } = e.nativeEvent as Partial<InputEvent>;
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
  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
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

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const moves: Record<string, number> = {
      ArrowLeft: active - 1,
      ArrowRight: active + 1,
      Home: 0,
      End: READING_LENGTH,
    };
    const target = moves[e.key];
    if (target !== undefined) {
      e.preventDefault();
      moveCaret(target);
    }
  };

  const handleCellPointer = (index: number) => (e: PointerEvent<HTMLSpanElement>) => {
    if (!isEdit) return;
    e.preventDefault(); // keep focus on the input, don't let the cell take it
    moveCaret(index);
    inputRef.current?.focus();
  };

  const rootClass = [styles.root, styles[size], isEdit ? styles.edit : '']
    .filter(Boolean)
    .join(' ');

  const renderCell = (digit: string, index: number) => {
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
function firstBlank(cells: Cells): number {
  const i = cells.indexOf('');
  return i === -1 ? cells.length : i;
}

export default MeterCounter;
