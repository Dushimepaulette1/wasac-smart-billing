import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ReadingHeld from './ReadingHeld';
import { I18nProvider } from '../../i18n/I18nProvider';
import { normalizeReading } from '../../utils/reading';

const renderAt = (state) =>
  render(
    <I18nProvider locale="en">
      <MemoryRouter
        initialEntries={[{ pathname: '/submit/held', state }]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/submit/held" element={<ReadingHeld />} />
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );

describe('ReadingHeld', () => {
  it('reassures without accusing, and shows the reading that was sent', () => {
    renderAt({ cells: normalizeReading('00000444').cells, at: '2026-10-09' });
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent("We're checking this reading");
    expect(status).toHaveTextContent("You don't need to do anything. We'll text you within 24 hours.");
    expect(screen.getByText('Meter reading: 0.444 cubic metres')).toBeInTheDocument();
    expect(screen.getByText('Sent on 09/10/2026')).toBeInTheDocument();
    expect(screen.queryByText(/anomaly|suspicious|error/i)).not.toBeInTheDocument();
  });

  it('still explains itself after a reload, without the reading', () => {
    renderAt(undefined);
    expect(screen.getByText("We're checking this reading")).toBeInTheDocument();
    expect(screen.queryByText(/Meter reading/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to home' })).toBeInTheDocument();
  });
});
