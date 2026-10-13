import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

async function renderScreen() {
  // Imported after vi.doMock, together, so Screen and the provider share one i18n context.
  const { default: Screen } = await import('./Screen');
  const { I18nProvider } = await import('../../i18n/I18nProvider');
  render(
    <I18nProvider locale="en">
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Screen title="Your bill">
          <p>content</p>
        </Screen>
      </MemoryRouter>
    </I18nProvider>,
  );
}

afterEach(() => {
  vi.resetModules();
  vi.doUnmock('../../config');
});

describe('Screen demo label', () => {
  it('says "Demo data" while a DEMO- household is used', async () => {
    vi.doMock('../../config', async (orig) => ({ ...(await orig<object>()), IS_DEMO_HOUSEHOLD: true }));
    await renderScreen();
    expect(screen.getByText('Demo data')).toBeInTheDocument();
  });

  it('shows no label for a real household', async () => {
    vi.doMock('../../config', async (orig) => ({ ...(await orig<object>()), IS_DEMO_HOUSEHOLD: false }));
    await renderScreen();
    expect(screen.queryByText('Demo data')).not.toBeInTheDocument();
  });
});
