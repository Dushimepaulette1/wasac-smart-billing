import en from '../../src/i18n/locales/en.json';
import rw from '../../src/i18n/locales/rw.json';
import { lookup, translate, TODO_MARK } from '../../src/i18n/I18nProvider';
import { makeFormatters } from '../../src/i18n/format';

describe('locale files', () => {
  it.each([
    ['rw', rw],
  ])('when checking %s, should have exactly the English keys (run npm run i18n:sync)', (_, messages) => {
    expect(Object.keys(messages).sort()).toEqual(Object.keys(en).sort());
  });

  it.each([
    ['rw', rw],
  ])('when checking %s, should have a translation or the TODO mark, never an empty value', (_, messages) => {
    for (const value of Object.values(messages)) {
      expect(typeof value).toBe('string');
      expect(value.trim()).not.toBe('');
    }
  });

  it('when checking English, should have no TODO marks', () => {
    expect(Object.values(en).some((v) => v.startsWith(TODO_MARK))).toBe(false);
  });
});

describe('translate', () => {
  it('when the string is translated, should use Kinyarwanda', () => {
    expect(translate('rw', 'action.retry')).toBe('Ongera ugerageze');
  });

  it('when a key is still TODO or missing, should fall back to English', () => {
    expect(lookup({ 'action.retry': TODO_MARK }, 'action.retry')).toBe(en['action.retry']);
    expect(lookup({}, 'action.retry')).toBe(en['action.retry']);
  });

  it('when a key is missing everywhere, should show the key itself', () => {
    expect(translate('en', 'no.such.key')).toBe('no.such.key');
  });

  it('when given values, should fill the placeholders', () => {
    expect(translate('en', 'pay.action', { amount: 'RWF 4,500' })).toBe('Pay RWF 4,500');
  });

  it('when a value is missing, should leave its placeholder visible', () => {
    expect(translate('en', 'pay.action', {})).toBe('Pay {amount}');
  });
});

describe('formatters', () => {
  const f = makeFormatters((key) => translate('en', key));

  it('when formatting money, should write RWF with no decimals', () => {
    expect(f.rwf(4500)).toBe('RWF 4,500');
    expect(f.rwf(9939.6)).toBe('RWF 9,940');
  });

  it('when formatting a volume, should write one decimal with m³', () => {
    expect(f.volume(12.44)).toBe('12.4 m³');
    expect(f.volume(20)).toBe('20.0 m³');
  });

  it('when formatting a date, should write DD/MM/YYYY without shifting the day', () => {
    expect(f.date('2026-09-14T23:30:00')).toBe('14/09/2026');
    expect(f.date(null)).toBe('');
  });

  it('when naming a month, should use the translation files', () => {
    expect(f.monthYear('2026-09-14T10:00:00')).toBe('September 2026');
  });

  it('when the language is Kinyarwanda, should write numbers as WASAC bills do', () => {
    // Kinyarwanda's own convention would print "4.500" and make 565.846 m³ look like 565 thousand.
    const fRw = makeFormatters((key) => translate('rw', key));
    expect(fRw.rwf(4500)).toBe('RWF 4,500');
    expect(fRw.volume(12.44)).toBe('12.4 m³');
  });
});
