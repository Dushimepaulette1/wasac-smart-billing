import { useState } from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import MeterCounter from '../../src/components/MeterCounter/MeterCounter';
import { normalizeReading } from '../../src/utils/reading';

const LABELS = {
  reading: 'Meter reading',
  cubicMetres: 'm³',
  litres: 'litres',
  cubicMetresLong: 'cubic metres',
};

function Editable({ raw }: { raw: string }) {
  const [cells, setCells] = useState(normalizeReading(raw).cells);
  return <MeterCounter cells={cells} labels={LABELS} mode="edit" onChange={setCells} />;
}

// jsdom's input events carry no inputType/data, so build them by hand.
function sendInput(input: HTMLInputElement, inputType: string, data: string | null = null) {
  const event = new Event('input', { bubbles: true });
  Object.defineProperty(event, 'inputType', { value: inputType });
  Object.defineProperty(event, 'data', { value: data });
  // React listens for "input" to fire onChange on text inputs.
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(input, inputType.startsWith('delete') ? input.value.slice(0, -1) : input.value + (data ?? ''));
  act(() => {
    input.dispatchEvent(event);
  });
}

const cellElements = (container: HTMLElement) => [...container.querySelectorAll('[class*="cell"]')];

const cellsOf = (container: HTMLElement) => cellElements(container).map((c) => c.textContent);

/** Give the cells side-by-side positions (jsdom has no layout): cell i spans x = 10i..10i+9. */
function placeCells(container: HTMLElement) {
  cellElements(container).forEach((cell, i) => {
    cell.getBoundingClientRect = () => ({ left: i * 10, right: i * 10 + 9 }) as DOMRect;
  });
}

describe('MeterCounter', () => {
  it('when only displaying, should announce the whole reading once', () => {
    render(<MeterCounter cells={normalizeReading('02813450').cells} labels={LABELS} />);
    expect(screen.getByText('Meter reading: 2,813.450 cubic metres')).toBeInTheDocument();
  });

  it('when the reading is short, should pad it with leading zeros', () => {
    const { container } = render(
      <MeterCounter cells={normalizeReading('565846').cells} labels={LABELS} />,
    );
    expect(cellsOf(container).join('')).toBe('00565846');
  });

  it('when a digit is tapped, should let the tap reach the input so phones open the keyboard', () => {
    render(<Editable raw="565846" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    expect(getComputedStyle(input).pointerEvents).not.toBe('none');
    expect(input).toHaveAttribute('inputmode', 'numeric');
  });

  it('when a digit is typed over, should replace it, and Backspace should undo it', () => {
    const { container } = render(<Editable raw="565846" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    // The tap lands on the input (so phones open the keyboard); the cell is found by position.
    placeCells(container);
    fireEvent.pointerDown(input, { clientX: 25 });

    sendInput(input, 'insertText', '7');
    expect(input.value).toBe('00765846');

    sendInput(input, 'deleteContentBackward');
    expect(cellsOf(container)).toEqual(['0', '0', '', '6', '5', '8', '4', '6']);
  });

  it('when the counter is blank, should fill digit by digit, and Backspace should clear the last', () => {
    render(<Editable raw="not a reading" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    act(() => input.focus());
    for (const d of '02813450') sendInput(input, 'insertText', d);
    expect(input.value).toBe('02813450');

    sendInput(input, 'deleteContentBackward');
    expect(input.value).toBe('0281345');
  });

  it('when a short reading is pasted, should pad it the way the digit reader does', () => {
    render(<Editable raw="not a reading" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    fireEvent.paste(input, { clipboardData: { getData: () => '565 846' } });
    expect(input.value).toBe('00565846');
  });
});
