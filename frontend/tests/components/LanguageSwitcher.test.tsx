import { fireEvent, render, screen } from '@testing-library/react';
import LanguageSwitcher from '../../src/components/LanguageSwitcher/LanguageSwitcher';
import { I18nProvider } from '../../src/i18n/I18nProvider';

afterEach(() => window.localStorage.clear());

describe('LanguageSwitcher', () => {
  it('defaults to Kinyarwanda on a new device', () => {
    window.localStorage.clear();
    render(<I18nProvider><LanguageSwitcher /></I18nProvider>);
    expect(screen.getByRole('group', { name: 'Ururimi' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ikinyarwanda' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.lang).toBe('rw');
  });

  it('restores a saved English choice', () => {
    window.localStorage.setItem('wasac.locale', 'en');
    render(<I18nProvider><LanguageSwitcher /></I18nProvider>);
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.lang).toBe('en');
  });

  it('when switching, should show short names, mark the current one and remember the choice', () => {
    render(
      <I18nProvider locale="en">
        <LanguageSwitcher />
      </I18nProvider>,
    );
    const kiny = screen.getByRole('button', { name: 'Ikinyarwanda' });
    const eng = screen.getByRole('button', { name: 'English' });
    expect(kiny).toHaveTextContent('Kiny');
    expect(eng).toHaveTextContent('Eng');
    expect(eng).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(kiny);
    expect(screen.getByRole('button', { name: 'Ikinyarwanda' })).toHaveAttribute('aria-pressed', 'true');
  });
});
