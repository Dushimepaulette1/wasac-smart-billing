import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReadingGate from '../../src/household/ReadingGate';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { api, ApiError } from '../../src/api/client';
import { makeCustomer } from '../support/fixtures';
import { TestHousehold } from '../support/household';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, getCustomer: vi.fn() } };
});

const renderGate = () =>
  render(
    <I18nProvider locale="en">
      <TestHousehold>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <ReadingGate>
            <p>Camera page</p>
          </ReadingGate>
        </MemoryRouter>
      </TestHousehold>
    </I18nProvider>,
  );

afterEach(() => window.localStorage.clear());

describe('ReadingGate', () => {
  it('when a reading can be sent, should open the camera', async () => {
    vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer());
    renderGate();
    expect(await screen.findByText('Camera page')).toBeInTheDocument();
  });

  it('when a reading is waiting for an officer, should say so instead of opening the camera', async () => {
    vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ reading_pending: true }));
    renderGate();
    expect(await screen.findByText(/You can send a new one after the decision/)).toBeInTheDocument();
    expect(screen.queryByText('Camera page')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'See messages' })).toBeInTheDocument();
  });

  it("when this month's reading is in, should say when the next one opens", async () => {
    vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ next_reading_from: '2026-11-16T09:00:00' }));
    renderGate();
    expect(await screen.findByText('You can send your next reading from 16/11/2026.', { exact: false })).toBeInTheDocument();
    expect(screen.queryByText('Camera page')).not.toBeInTheDocument();
  });

  it('when the check fails, should let the household carry on', async () => {
    vi.mocked(api.getCustomer).mockRejectedValue(new ApiError('offline'));
    renderGate();
    expect(await screen.findByText('Camera page')).toBeInTheDocument();
  });
});
