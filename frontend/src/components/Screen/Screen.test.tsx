import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Screen from './Screen';
import { I18nProvider } from '../../i18n/I18nProvider';
import { TEST_ACCOUNT, TestHousehold } from '../../test/household';

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
  it('says "Demo data" while a DEMO- household is signed in', () => {
    renderScreen(true);
    expect(screen.getByText('Demo data')).toBeInTheDocument();
  });

  it('shows no label for a real household', () => {
    renderScreen(false);
    expect(screen.queryByText('Demo data')).not.toBeInTheDocument();
  });
});
