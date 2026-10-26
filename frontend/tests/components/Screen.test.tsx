import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Screen from '../../src/components/Screen/Screen';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TEST_ACCOUNT, TestHousehold } from '../support/household';

function renderScreen(isDemo: boolean) {
  render(
    <I18nProvider locale="en">
      <TestHousehold account={{ ...TEST_ACCOUNT, is_demo: isDemo }}>
        <MemoryRouter initialEntries={['/bill']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route
              path="/bill"
              element={
                <Screen title="Your bill" back="/home">
                  <p>content</p>
                </Screen>
              }
            />
            <Route path="/home" element={<p>Home page</p>} />
          </Routes>
        </MemoryRouter>
      </TestHousehold>
    </I18nProvider>,
  );
}

afterEach(() => window.localStorage.clear());

describe('Screen', () => {
  it('when a DEMO- household is signed in, should show no demo label', () => {
    renderScreen(true);
    expect(screen.queryByText('Demo data')).not.toBeInTheDocument();
  });

  it('when Back is pressed, should go to the page given', () => {
    renderScreen(false);
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(screen.getByText('Home page')).toBeInTheDocument();
  });
});
