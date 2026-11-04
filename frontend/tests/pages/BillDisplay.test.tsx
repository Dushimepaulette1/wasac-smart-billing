import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import BillDisplay from '../../src/pages/BillDisplay/BillDisplay';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import loadBill, { type BillView } from '../../src/household/loadBill';
import { makeBill } from '../support/fixtures';

vi.mock('../../src/household/loadBill', () => ({ default: vi.fn() }));

const view = (bill: BillView['bill']): BillView => ({
  bill, tiers: [], vat: 0, serviceCharge: 1000, periodStart: null, reading: null, history: [bill], leakPercent: null,
});

function renderBill(bill: BillView['bill'], vat = 0, leakPercent: number | null = null) {
  vi.mocked(loadBill).mockResolvedValue({ ...view(bill), vat, leakPercent });
  render(
    <I18nProvider locale="en">
      <TestHousehold>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <BillDisplay />
        </MemoryRouter>
      </TestHousehold>
    </I18nProvider>,
  );
}

describe('BillDisplay', () => {
  it('when a bill was corrected, should show the original, the correction, the credit and the balance', async () => {
    renderBill(makeBill({
      amount_due: 21375, charges: 13160, credit_used: 2000, outstanding: 11160, payment_status: 'unpaid',
      adjustments: [{ amount_delta: -8215, consumption_after: 21.46, reason: 'Read again on site', at: '2026-10-01T08:00:00' }],
    }));
    expect(await screen.findByText('Correction: Read again on site')).toBeInTheDocument();
    expect(screen.getByText('−RWF 8,215')).toBeInTheDocument();
    expect(screen.getByText('Credit used')).toBeInTheDocument();
    expect(screen.getByText('RWF 21,375')).toBeInTheDocument();
    expect(screen.getByText('Balance')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pay RWF 11,160' })).toBeInTheDocument();
  });

  it('when a bill has no correction, should show no balance line', async () => {
    renderBill(makeBill({ amount_due: 6460, outstanding: 6460, payment_status: 'unpaid' }));
    expect(await screen.findByRole('button', { name: 'Pay RWF 6,460' })).toBeInTheDocument();
    expect(screen.queryByText('Balance')).not.toBeInTheDocument();
  });

  it('when a bill is on the WASAC tariff, should show the water without VAT, then VAT, then the service charge', async () => {
    // 20 m3: RWF 12,500 of water at the rates without VAT, RWF 2,290 VAT, RWF 1,000 service charge.
    renderBill(makeBill({ amount_due: 15790, outstanding: 15790, payment_status: 'unpaid' }), 2290);
    expect(await screen.findByText('VAT on water')).toBeInTheDocument();
    expect(screen.getByText('RWF 12,500')).toBeInTheDocument();
    expect(screen.getByText('RWF 2,290')).toBeInTheDocument();
    expect(screen.getByText('RWF 15,790')).toBeInTheDocument();
  });

  it('when a bill has no VAT, should show no VAT line', async () => {
    renderBill(makeBill({ amount_due: 6460, outstanding: 6460, payment_status: 'unpaid' }));
    await screen.findByRole('button', { name: 'Pay RWF 6,460' });
    expect(screen.queryByText('VAT on water')).not.toBeInTheDocument();
  });

  it('when this bill looks like a leak, should say how far above usual it is', async () => {
    renderBill(makeBill({ amount_due: 25000, outstanding: 25000, payment_status: 'unpaid' }), 0, 67);
    expect(await screen.findByText('This is about 67% more than your usual use. Check for leaks.')).toBeInTheDocument();
  });

  it('when this bill is as usual, should show no leak line', async () => {
    renderBill(makeBill({ amount_due: 6460, outstanding: 6460, payment_status: 'unpaid' }));
    await screen.findByRole('button', { name: 'Pay RWF 6,460' });
    expect(screen.queryByText(/more than your usual use/)).not.toBeInTheDocument();
  });
});
