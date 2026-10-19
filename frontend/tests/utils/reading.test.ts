import {
  normalizeReading,
  cellsFromCubicMetres,
  isComplete,
  cellsToDigits,
  formatReading,
} from '../../src/utils/reading';

describe('normalizeReading', () => {
  it('when the reading has 8 digits, should keep it as it is', () => {
    expect(normalizeReading('02813450')).toEqual({
      cells: ['0', '2', '8', '1', '3', '4', '5', '0'],
      needsCheck: false,
      raw: '02813450',
    });
  });

  it('when leading zeros were dropped, should pad them back', () => {
    const { cells, needsCheck } = normalizeReading('565846');
    expect(cellsToDigits(cells)).toBe('00565846');
    expect(needsCheck).toBe(false);
  });

  it('when the reading is a single digit, should pad it', () => {
    expect(cellsToDigits(normalizeReading('7').cells)).toBe('00000007');
  });

  it('when the reading has spaces around it, should trim them', () => {
    expect(cellsToDigits(normalizeReading(' 565846 ').cells)).toBe('00565846');
  });

  it.each([
    ['too many digits', '123456789'],
    ['non-digits', '56A846'],
    ['a decimal point', '2813.450'],
    ['empty', ''],
    ['null', null],
    ['undefined', undefined],
  ])('when the reading has %s, should ask the household to check the numbers', (_, raw) => {
    const { cells, needsCheck } = normalizeReading(raw);
    expect(needsCheck).toBe(true);
    expect(cells).toEqual(['', '', '', '', '', '', '', '']);
  });

  it('when the length is wrong, should keep the raw reading so it can be shown', () => {
    expect(normalizeReading(' 005162454 ')).toEqual({
      cells: ['', '', '', '', '', '', '', ''],
      needsCheck: true,
      raw: '005162454',
    });
  });

  it('when the reader returned nothing, should give an empty raw reading', () => {
    expect(normalizeReading(null).raw).toBe('');
  });
});

describe('cellsFromCubicMetres', () => {
  it('when given cubic metres, should split them into wheel digits', () => {
    expect(cellsToDigits(cellsFromCubicMetres(2813.45))).toBe('02813450');
  });

  it('when given whole cubic metres, should handle them', () => {
    expect(cellsToDigits(cellsFromCubicMetres(2813))).toBe('02813000');
  });

  it('when the value cannot be shown on the meter, should return blanks', () => {
    expect(isComplete(cellsFromCubicMetres(100000))).toBe(false);
    expect(isComplete(cellsFromCubicMetres(-1))).toBe(false);
    expect(isComplete(cellsFromCubicMetres(NaN))).toBe(false);
  });
});

describe('formatReading', () => {
  const cells = normalizeReading('02813450').cells;

  it('when formatting, should use English number style', () => {
    expect(formatReading(cells)).toBe('2,813.450');
  });

  it('when formatting, should drop leading cubic-metre zeros but keep all litre digits', () => {
    expect(formatReading(normalizeReading('565846').cells)).toBe('565.846');
    expect(formatReading(normalizeReading('00000045').cells)).toBe('0.045');
  });

  it('when a cell is blank, should be empty', () => {
    const partial = [...cells];
    partial[3] = '';
    expect(formatReading(partial)).toBe('');
  });
});
