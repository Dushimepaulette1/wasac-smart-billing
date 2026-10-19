import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ReadingHeld from '../../src/pages/ReadingHeld/ReadingHeld';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { normalizeReading } from '../../src/utils/reading';

const renderAt = (state: unknown) =>
  render(
    <I18nProvider locale="en">
<TestHousehold>
      <MemoryRouter
        initialEntries={[{ pathname: '/submit/held', state }]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/submit/held" element={<ReadingHeld />} />
        </Routes>
      </MemoryRouter>
    </TestHousehold>
</I18nProvider>,
  );

describe('ReadingHeld', () => {
  it('when a reading is held, should reassure without accusing and show the reading', () => {
    renderAt({ cells: normalizeReading('00000444').cells, at: '2026-10-09' });
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent("We're checking this reading");
    expect(status).toHaveTextContent('A WASAC officer is checking this reading.');
    expect(status).toHaveTextContent('the result will appear in Messages');
    expect(status).not.toHaveTextContent(/text you|24 hours/i);
    expect(screen.getByText('Meter reading: 0.444 cubic metres')).toBeInTheDocument();
    expect(screen.getByText('Sent on 09/10/2026')).toBeInTheDocument();
    expect(screen.queryByText(/anomaly|suspicious|error/i)).not.toBeInTheDocument();
  });

  it('when the page is reloaded, should still explain itself without the reading', () => {
    renderAt(undefined);
    expect(screen.getByText("We're checking this reading")).toBeInTheDocument();
    expect(screen.queryByText(/Meter reading/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to home' })).toBeInTheDocument();
  });
});
