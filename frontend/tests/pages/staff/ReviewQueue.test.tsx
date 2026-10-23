import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ReviewQueue from '../../../src/pages/staff/ReviewQueue';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';
import type { ReviewItem } from '../../../src/api/types';
import { makeFlag } from '../../support/fixtures';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, reviewQueue: vi.fn(), resolveFlag: vi.fn() } };
});

const item = (id: number, name: string, flag: Parameters<typeof makeFlag>[0]): ReviewItem => ({
  flag: makeFlag({ id, ...flag }),
  reading_m3: 565.846,
  submitted_at: '2026-10-20T08:00:00',
  reading_confidence: null,
  customer_id: `CUST-${id}`,
  customer_name: name,
  sector: 'Kicukiro',
  history: [],
});

function renderQueue() {
  const user = { username: 'officer1', full_name: 'Officer One', role: 'officer' };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
  return render(
    <I18nProvider locale="en">
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <ReviewQueue />
        </MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  window.sessionStorage.clear();
});

describe('ReviewQueue', () => {
  it('when a reading is held, should offer accept and reject', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([item(1, 'Held House', { anomaly_type: 'SPIKE' })]);
    renderQueue();
    expect(await screen.findByRole('button', { name: /accept reading/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /close: followed up/i })).not.toBeInTheDocument();
  });

  it('when an already-billed reading needs follow-up, should offer only close and send no outcome', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([
      item(2, 'Stuck House', { anomaly_type: 'METER_STUCK', reading_status: 'anomaly_flagged' }),
    ]);
    vi.mocked(api.resolveFlag).mockResolvedValue({
      ...makeFlag({ id: 2, status: 'resolved' }),
      outcome: null,
      reading_status: 'anomaly_flagged',
      bill_id: null,
      amount_due: null,
      actions: [],
    });
    renderQueue();
    const close = await screen.findByRole('button', { name: /close: followed up/i });
    expect(screen.queryByRole('button', { name: /accept reading/i })).not.toBeInTheDocument();

    vi.useFakeTimers();
    fireEvent.keyDown(document.body, { key: 'a' }); // accepting is not offered here
    expect(screen.queryByText(/accepting/i)).not.toBeInTheDocument();
    fireEvent.click(close);
    expect(screen.getByText(/closing the follow-up for stuck house/i)).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });
    expect(api.resolveFlag).toHaveBeenCalledWith(2, null);
    expect(screen.getByText(/closed the follow-up for stuck house/i)).toBeInTheDocument();
  });
});
