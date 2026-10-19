import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Screen from '../../src/components/Screen/Screen';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TEST_ACCOUNT, TestHousehold } from '../support/household';

function renderScreen(isDemo: boolean) {
  render(
    <I18nProvider locale="en">
      <TestHousehold account={{ ...TEST_ACCOUNT, is_demo: isDemo }}>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Screen title="Your bill">
            <p>content</p>
          </Screen>
        </MemoryRouter>
      </TestHousehold>
    </I18nProvider>,
  );
}

afterEach(() => window.localStorage.clear());

describe('Screen demo label', () => {
  it('when a DEMO- household is signed in, should say "Demo data"', () => {
    renderScreen(true);
    expect(screen.getByText('Demo data')).toBeInTheDocument();
  });

  it('when a real household is signed in, should show no label', () => {
    renderScreen(false);
    expect(screen.queryByText('Demo data')).not.toBeInTheDocument();
  });
});
