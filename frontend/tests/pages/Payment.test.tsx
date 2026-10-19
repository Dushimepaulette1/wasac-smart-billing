import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Payment from '../../src/pages/Payment/Payment';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { api, ApiError } from '../../src/api/client';
import { makeBill, makeCustomer } from '../support/fixtures';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, getBills: vi.fn(), getCustomer: vi.fn(), payBill: vi.fn() } };
});

const BILL = makeBill({ bill_id: 19, amount_due: 12400.5, payment_status: 'unpaid' });

function renderPayment() {
  return render(
    <I18nProvider locale="en">
<TestHousehold>
      <MemoryRouter
        initialEntries={['/payment?bill=19']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/payment" element={<Payment />} />
        </Routes>
      </MemoryRouter>
    </TestHousehold>
</I18nProvider>,
  );
}

beforeEach(() => {
  vi.mocked(api.getBills).mockResolvedValue([BILL]);
  vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ phone: '+250788123456' }));
});

describe('Payment', () => {
  it('when paying, should name the amount on the button and the number that pays', async () => {
    renderPayment();
    expect(await screen.findByRole('button', { name: 'Pay RWF 12,401' })).toBeEnabled();
    expect(screen.getByText(/078 812 3456/)).toBeInTheDocument();
  });

  it('when payment succeeds, should show Paid with the transaction id', async () => {
    vi.mocked(api.payBill).mockResolvedValue({
      success: true,
      bill_id: 19,
      transaction_id: 'MOMO-000019-RW',
      amount_paid: 12400.5,
      message: 'Payment successful',
    });
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('heading', { name: 'Paid' })).toBeInTheDocument();
    expect(screen.getByText('You paid RWF 12,401.')).toBeInTheDocument();
    expect(screen.getByText('MOMO-000019-RW')).toHaveClass('code');
  });

  it('when the connection drops, should not claim the household was not charged', async () => {
    vi.mocked(api.payBill).mockRejectedValue(new ApiError('offline'));
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('alert')).toHaveTextContent('Check your bills before you try again');
    expect(screen.queryByText(/not been charged|not charged/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'See your bills' })).toBeInTheDocument();
  });

  it('when the bill is already paid, should show it as paid without a Pay button', async () => {
    vi.mocked(api.getBills).mockResolvedValue([{ ...BILL, payment_status: 'paid' }]);
    renderPayment();
    expect(await screen.findByText('This bill is already paid.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Pay/ })).not.toBeInTheDocument();
  });
});
