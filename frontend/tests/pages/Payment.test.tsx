import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Payment from '../../src/pages/Payment/Payment';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { api, ApiError } from '../../src/api/client';
import { makeBill, makeCustomer } from '../support/fixtures';
import type { Payment as PaymentAttempt } from '../../src/api/types';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, getBills: vi.fn(), getCustomer: vi.fn(), payBill: vi.fn(), getPayment: vi.fn() } };
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

function attempt(overrides: Partial<PaymentAttempt>): PaymentAttempt {
  return {
    id: 5, bill_id: 19, provider: 'simulated', status: 'pending', amount: 12400.5, currency: 'RWF',
    transaction_id: null, reason: null, already_paid: false, ...overrides,
  };
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
    vi.mocked(api.payBill).mockResolvedValue(attempt({ status: 'successful', provider: 'momo', transaction_id: 'MOMO-000019-RW' }));
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('heading', { name: 'Paid' })).toBeInTheDocument();
    expect(screen.getByText('You paid RWF 12,401.')).toBeInTheDocument();
    expect(screen.getByText('MOMO-000019-RW')).toHaveClass('code');
    expect(screen.queryByText(/Test payment/)).not.toBeInTheDocument(); // real money
  });

  it('when MTN sends a PIN prompt, should wait for the approval, then show Paid', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.payBill).mockResolvedValue(attempt({ status: 'pending', provider: 'momo_sandbox' }));
    vi.mocked(api.getPayment)
      .mockResolvedValueOnce(attempt({ status: 'pending', provider: 'momo_sandbox' }))
      .mockResolvedValueOnce(attempt({ status: 'successful', provider: 'momo_sandbox', transaction_id: '987654321' }));
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('heading', { name: 'Approve the payment on your phone' })).toBeInTheDocument();
    expect(screen.getByText(/sent a request to 078 812 3456 to pay RWF 12,401/)).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
    await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
    expect(screen.getByRole('heading', { name: 'Paid' })).toBeInTheDocument();
    expect(screen.getByText('987654321')).toBeInTheDocument();
    expect(screen.getByText('Test payment: no real money was taken.')).toBeInTheDocument();
    vi.useRealTimers();
  });

  it('when the payer declines, should say nothing was taken and allow another try', async () => {
    vi.mocked(api.payBill).mockResolvedValue(attempt({ status: 'failed', provider: 'momo', reason: 'Payer not found' }));
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('alert')).toHaveTextContent('Nothing was taken from your account. You can try again. (Payer not found)');
    expect(screen.getByRole('button', { name: 'Pay RWF 12,401' })).toBeEnabled();
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
