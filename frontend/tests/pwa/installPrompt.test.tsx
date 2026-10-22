import { act, fireEvent, render, screen } from '@testing-library/react';
import InstallApp from '../../src/pwa/InstallApp';
import { isIosSafari, resetInstallPrompt } from '../../src/pwa/installPrompt';
import { registerServiceWorker } from '../../src/pwa/registerServiceWorker';
import { I18nProvider } from '../../src/i18n/I18nProvider';

const renderInstall = () =>
  render(
    <I18nProvider locale="en">
      <InstallApp />
    </I18nProvider>,
  );

/** A fake Chrome `beforeinstallprompt` event. */
function offerInstall() {
  const prompt = vi.fn().mockResolvedValue(undefined);
  const event = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
    prompt,
    userChoice: Promise.resolve({ outcome: 'accepted' as const }),
  });
  act(() => {
    window.dispatchEvent(event);
  });
  return { prompt, event };
}

afterEach(() => resetInstallPrompt());

describe('Install the app', () => {
  it('when the browser cannot install, should show nothing', () => {
    renderInstall();
    expect(screen.queryByRole('button', { name: 'Install the app' })).not.toBeInTheDocument();
  });

  it('when the browser offers to install, should show the button and open its dialog once', async () => {
    renderInstall();
    const { prompt, event } = offerInstall();
    expect(event.defaultPrevented).toBe(true); // our button instead of the browser's bar
    const button = await screen.findByRole('button', { name: 'Install the app' });
    await act(async () => {
      fireEvent.click(button);
    });
    expect(prompt).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Install the app' })).not.toBeInTheDocument();
  });

  it('when the app has been installed, should hide the button', async () => {
    renderInstall();
    offerInstall();
    await screen.findByRole('button', { name: 'Install the app' });
    act(() => {
      window.dispatchEvent(new Event('appinstalled'));
    });
    expect(screen.queryByRole('button', { name: 'Install the app' })).not.toBeInTheDocument();
  });

  it('when on an iPhone, should recognise Safari but not other iPhone browsers', () => {
    const safari = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';
    const chrome = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0 Mobile/15E148 Safari/604.1';
    const android = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36';
    expect(isIosSafari(safari)).toBe(true);
    expect(isIosSafari(chrome)).toBe(false);
    expect(isIosSafari(android)).toBe(false);
  });
});

describe('registerServiceWorker', () => {
  it('when developing, should not register (a cached app would hide edits)', () => {
    expect(registerServiceWorker(false, { serviceWorker: {} } as unknown as Navigator)).toBe(false);
  });

  it('when the browser has no service workers, should not register', () => {
    expect(registerServiceWorker(true, {} as Navigator)).toBe(false);
  });

  it('when in production, should register /sw.js once the page has loaded', () => {
    const register = vi.fn().mockResolvedValue(undefined);
    expect(registerServiceWorker(true, { serviceWorker: { register } } as unknown as Navigator)).toBe(true);
    window.dispatchEvent(new Event('load'));
    expect(register).toHaveBeenCalledWith('/sw.js');
  });
});
