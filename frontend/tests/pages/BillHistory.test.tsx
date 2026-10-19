import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BillHistory from '../../src/pages/BillHistory/BillHistory';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { api } from '../../src/api/client';
import { makeBill } from '../support/fixtures';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, getBills: vi.fn() } };
});

const renderHistory = () =>
  render(
    <I18nProvider locale="en">
<TestHousehold>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <BillHistory />
      </MemoryRouter>
    </TestHousehold>
</I18nProvider>,
  );

describe('BillHistory', () => {
  it('when there are bills, should list them newest first, linked, with the paid state in words', async () => {
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

  it('when two bills share a month, should name them by date', async () => {
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

  it('when there are no bills, should invite the first reading', async () => {
    vi.mocked(api.getBills).mockResolvedValue([]);
    renderHistory();
    expect(await screen.findByText('No bills yet. Take your first meter photo.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Read your meter' })).toBeInTheDocument();
  });
});
