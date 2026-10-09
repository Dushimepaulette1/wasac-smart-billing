import { useState } from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import MeterCounter from './MeterCounter';
import { normalizeReading } from '../../utils/reading';

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

function cellAt(container: HTMLElement, index: number): Element {
  const cell = cellElements(container)[index];
  if (!cell) throw new Error(`No counter cell ${index}`);
  return cell;
}

describe('MeterCounter', () => {
  it('speaks the whole reading once in display mode', () => {
    render(<MeterCounter cells={normalizeReading('02813450').cells} labels={LABELS} />);
    expect(screen.getByText('Meter reading: 2,813.450 cubic metres')).toBeInTheDocument();
  });

  it('shows a short reading padded with leading zeros', () => {
    const { container } = render(
      <MeterCounter cells={normalizeReading('565846').cells} labels={LABELS} />,
    );
    expect(cellsOf(container).join('')).toBe('00565846');
  });

  it('overwrites the tapped digit, and Backspace undoes it', () => {
    const { container } = render(<Editable raw="565846" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    fireEvent.pointerDown(cellAt(container, 2));

    sendInput(input, 'insertText', '7');
    expect(input.value).toBe('00765846');

    sendInput(input, 'deleteContentBackward');
    expect(cellsOf(container)).toEqual(['0', '0', '', '6', '5', '8', '4', '6']);
  });

  it('fills a blank counter digit by digit and clears the last on Backspace', () => {
    render(<Editable raw="not a reading" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    act(() => input.focus());
    for (const d of '02813450') sendInput(input, 'insertText', d);
    expect(input.value).toBe('02813450');

    sendInput(input, 'deleteContentBackward');
    expect(input.value).toBe('0281345');
  });

  it('pads a pasted short reading the same way as the digit reader', () => {
    render(<Editable raw="not a reading" />);
    const input = screen.getByLabelText<HTMLInputElement>('Meter reading');
    fireEvent.paste(input, { clipboardData: { getData: () => '565 846' } });
    expect(input.value).toBe('00565846');
  });
});
