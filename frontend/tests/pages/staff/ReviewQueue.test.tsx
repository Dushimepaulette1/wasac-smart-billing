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
  return { ...actual, api: { ...actual.api, reviewQueue: vi.fn(), resolveFlag: vi.fn(), readingPhoto: vi.fn() } };
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
  it('when rejecting, should ask why and send the reason', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([item(5, 'Reject House', { anomaly_type: 'SPIKE', reading_status: 'pending_review' })]);
    vi.mocked(api.resolveFlag).mockClear();
    vi.mocked(api.resolveFlag).mockResolvedValue({ amount_due: null } as Awaited<ReturnType<typeof api.resolveFlag>>);
    renderQueue();
    fireEvent.click(await screen.findByRole('button', { name: /reject, ask for a new photo/i }));
    expect(api.resolveFlag).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Why are you rejecting this reading?'), { target: { value: 'other' } });
    const confirmReject = screen.getByRole('button', { name: 'Reject the reading' });
    expect(confirmReject).toBeDisabled(); // a typed reason is needed
    fireEvent.change(screen.getByLabelText('The reason'), { target: { value: 'Meter was replaced' } });
    vi.useFakeTimers();
    fireEvent.click(confirmReject);
    await act(async () => { vi.runAllTimers(); });
    expect(api.resolveFlag).toHaveBeenCalledWith(5, 'reject', 'Meter was replaced');
  });

  it('when the server gives the previous reading, should show it', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([{ ...item(6, 'Prev House', { anomaly_type: 'MISREAD_SUSPECTED' }), previous_reading_m3: 431.46 }]);
    renderQueue();
    expect(await screen.findByText('431.460 m³')).toBeInTheDocument();
  });

  it('when the household lowered the photo reading, should show both readings with the changed wheels', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([{
      ...item(4, 'Edited House', { anomaly_type: 'EDITED_DOWN' }),
      reader_digits: '00443520', household_digits: '00442520', changed_positions: [4], edited_by_household: true,
    }]);
    renderQueue();
    expect(await screen.findByLabelText('Read 00443520, sent 00442520')).toBeInTheDocument();
    expect(screen.getAllByText('Lowered from the photo\'s reading').length).toBeGreaterThan(0);
  });

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

  it('when the reading came from a photo, should show the photo and what the reader read', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:photo');
    URL.revokeObjectURL = vi.fn();
    vi.mocked(api.readingPhoto).mockResolvedValue(new Blob(['jpeg'], { type: 'image/jpeg' }));
    vi.mocked(api.reviewQueue).mockResolvedValue([
      { ...item(3, 'Photo House', { anomaly_type: 'SPIKE' }), reading_id: 41, photo_available: true,
        reader_digits: '00565846', edited_by_household: true },
    ]);
    renderQueue();
    const photo = await screen.findByRole('img', { name: /meter photo sent by photo house/i });
    expect(photo).toHaveAttribute('src', 'blob:photo');
    expect(api.readingPhoto).toHaveBeenCalledWith(41);
    expect(screen.getByText(/changed by the household/i)).toBeInTheDocument();
  });

  it('when no photo was kept, should say so', async () => {
    vi.mocked(api.reviewQueue).mockResolvedValue([item(4, 'Typed House', { anomaly_type: 'SPIKE' })]);
    renderQueue();
    expect(await screen.findByText(/no photo for this reading/i)).toBeInTheDocument();
  });
});
