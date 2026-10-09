import en from './locales/en.json';
import rw from './locales/rw.json';
import fr from './locales/fr.json';
import { translate, TODO_MARK } from './I18nProvider';
import { makeFormatters } from './format';

describe('locale files', () => {
  it.each([
    ['rw', rw],
    ['fr', fr],
  ])('%s has exactly the English keys (run npm run i18n:sync)', (_, messages) => {
    expect(Object.keys(messages).sort()).toEqual(Object.keys(en).sort());
  });

  it.each([
    ['rw', rw],
    ['fr', fr],
  ])('%s values are a translation or the TODO mark, never empty', (_, messages) => {
    for (const value of Object.values(messages)) {
      expect(typeof value).toBe('string');
      expect(value.trim()).not.toBe('');
    }
  });

  it('English has no TODO marks', () => {
    expect(Object.values(en).some((v) => v.startsWith(TODO_MARK))).toBe(false);
  });
});

describe('translate', () => {
  it('falls back to English for a key still marked TODO', () => {
    expect(translate('rw', 'action.retry')).toBe(en['action.retry']);
  });

  it('shows the key itself when it is missing everywhere', () => {
    expect(translate('en', 'no.such.key')).toBe('no.such.key');
  });

  it('fills placeholders', () => {
    expect(translate('en', 'pay.action', { amount: 'RWF 4,500' })).toBe('Pay RWF 4,500');
  });

  it('leaves a placeholder visible when no value is given', () => {
    expect(translate('en', 'pay.action', {})).toBe('Pay {amount}');
  });
});

describe('formatters', () => {
  const f = makeFormatters('en', (key) => translate('en', key));

  it('writes money as RWF with no decimals', () => {
    expect(f.rwf(4500)).toBe('RWF 4,500');
    expect(f.rwf(9939.6)).toBe('RWF 9,940');
  });

  it('writes volumes to one decimal with m³', () => {
    expect(f.volume(12.44)).toBe('12.4 m³');
    expect(f.volume(20)).toBe('20.0 m³');
  });

  it('writes dates as DD/MM/YYYY without shifting the day', () => {
    expect(f.date('2026-09-14T23:30:00')).toBe('14/09/2026');
    expect(f.date(null)).toBe('');
  });

  it('names the month from the translation files', () => {
    expect(f.monthYear('2026-09-14T10:00:00')).toBe('September 2026');
  });

  it('groups digits by locale for French', () => {
    const fFr = makeFormatters('fr', (key) => translate('fr', key));
    expect(fFr.rwf(4500).replace(/\s/g, ' ')).toBe('RWF 4 500');
  });
});
