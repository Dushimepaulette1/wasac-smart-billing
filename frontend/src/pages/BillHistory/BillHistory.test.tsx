import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BillHistory from './BillHistory';
import { I18nProvider } from '../../i18n/I18nProvider';
import { api } from '../../api/client';
import { makeBill } from '../../test/fixtures';

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, api: { ...actual.api, getBills: vi.fn() } };
});

const renderHistory = () =>
  render(
    <I18nProvider locale="en">
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <BillHistory />
      </MemoryRouter>
    </I18nProvider>,
  );

describe('BillHistory', () => {
  it('lists bills newest first, each linking to the bill, with paid state in words', async () => {
    vi.mocked(api.getBills).mockResolvedValue([
      makeBill({ bill_id: 21, consumption_m3: 0.7, amount_due: 1245, payment_status: 'unpaid', created_at: '2026-10-09T11:00:00' }),
      makeBill({ bill_id: 6, consumption_m3: 22, amount_due: 13587, payment_status: 'paid', created_at: '2026-09-09T09:38:11' }),
    ]);
    renderHistory();
    const october = await screen.findByRole('link', { name: /October 2026/ });
    expect(october).toHaveAttribute('href', '/bill?id=21');
    expect(october).toHaveTextContent('RWF 1,245');
    expect(october).toHaveTextContent('Not paid yet');
    expect(screen.getByRole('link', { name: /September 2026/ })).toHaveTextContent('Paid');
  });

  it('names bills by date when two share a month', async () => {
    vi.mocked(api.getBills).mockResolvedValue([
      makeBill({ bill_id: 22, consumption_m3: 0.7, amount_due: 1245, payment_status: 'paid', created_at: '2026-10-09T12:00:00' }),
      makeBill({ bill_id: 21, consumption_m3: 0.7, amount_due: 1245, payment_status: 'paid', created_at: '2026-10-02T12:00:00' }),
      makeBill({ bill_id: 6, consumption_m3: 22, amount_due: 13587, payment_status: 'paid', created_at: '2026-09-09T09:38:11' }),
    ]);
    renderHistory();
    expect(await screen.findByRole('link', { name: /09\/10\/2026/ })).toHaveAttribute('href', '/bill?id=22');
    expect(screen.getByRole('link', { name: /02\/10\/2026/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /September 2026/ })).toBeInTheDocument();
  });

  it('invites the first reading when there are no bills', async () => {
    vi.mocked(api.getBills).mockResolvedValue([]);
    renderHistory();
    expect(await screen.findByText('No bills yet. Take your first meter photo.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Read your meter' })).toBeInTheDocument();
  });
});
