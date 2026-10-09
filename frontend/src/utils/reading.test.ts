import {
  normalizeReading,
  cellsFromCubicMetres,
  isComplete,
  cellsToDigits,
  formatReading,
} from './reading';

describe('normalizeReading', () => {
  it('keeps an 8-digit reading as it is', () => {
    expect(normalizeReading('02813450')).toEqual({
      cells: ['0', '2', '8', '1', '3', '4', '5', '0'],
      needsCheck: false,
      raw: '02813450',
    });
  });

  it('left-pads a reading with dropped leading zeros', () => {
    const { cells, needsCheck } = normalizeReading('565846');
    expect(cellsToDigits(cells)).toBe('00565846');
    expect(needsCheck).toBe(false);
  });

  it('pads a single digit', () => {
    expect(cellsToDigits(normalizeReading('7').cells)).toBe('00000007');
  });

  it('trims surrounding spaces', () => {
    expect(cellsToDigits(normalizeReading(' 565846 ').cells)).toBe('00565846');
  });

  it.each([
    ['too many digits', '123456789'],
    ['non-digits', '56A846'],
    ['a decimal point', '2813.450'],
    ['empty', ''],
    ['null', null],
    ['undefined', undefined],
  ])('asks the household to check the numbers when %s', (_, raw) => {
    const { cells, needsCheck } = normalizeReading(raw);
    expect(needsCheck).toBe(true);
    expect(cells).toEqual(['', '', '', '', '', '', '', '']);
  });

  it('keeps the raw reading of a wrong-length result so it can be shown', () => {
    expect(normalizeReading(' 005162454 ')).toEqual({
      cells: ['', '', '', '', '', '', '', ''],
      needsCheck: true,
      raw: '005162454',
    });
  });

  it('gives an empty raw reading when the reader returned nothing', () => {
    expect(normalizeReading(null).raw).toBe('');
  });
});

describe('cellsFromCubicMetres', () => {
  it('splits cubic metres into wheel digits', () => {
    expect(cellsToDigits(cellsFromCubicMetres(2813.45))).toBe('02813450');
  });

  it('handles whole cubic metres from mock data', () => {
    expect(cellsToDigits(cellsFromCubicMetres(2813))).toBe('02813000');
  });

  it('returns blanks for values the meter cannot show', () => {
    expect(isComplete(cellsFromCubicMetres(100000))).toBe(false);
    expect(isComplete(cellsFromCubicMetres(-1))).toBe(false);
    expect(isComplete(cellsFromCubicMetres(NaN))).toBe(false);
  });
});

describe('formatReading', () => {
  const cells = normalizeReading('02813450').cells;

  it('formats in English', () => {
    expect(formatReading(cells, 'en')).toBe('2,813.450');
  });

  it('drops leading zeros of the cubic metres but keeps all litre digits', () => {
    expect(formatReading(normalizeReading('565846').cells, 'en')).toBe('565.846');
    expect(formatReading(normalizeReading('00000045').cells, 'en')).toBe('0.045');
  });

  it('formats in French', () => {
    expect(formatReading(cells, 'fr').replace(/\s/g, ' ')).toBe('2 813,450');
  });

  it('is empty while a cell is blank', () => {
    const partial = [...cells];
    partial[3] = '';
    expect(formatReading(partial, 'en')).toBe('');
  });
});
