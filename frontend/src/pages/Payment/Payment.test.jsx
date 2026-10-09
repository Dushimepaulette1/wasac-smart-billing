import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import Payment from './Payment';
import { I18nProvider } from '../../i18n/I18nProvider';
import { api } from '../../api/client';

jest.mock('../../api/client', () => {
  const actual = jest.requireActual('../../api/client');
  return { ...actual, api: { getBills: jest.fn(), getCustomer: jest.fn(), payBill: jest.fn() } };
});

const BILL = { bill_id: 19, consumption_m3: 20.5, amount_due: 12400.5, payment_status: 'unpaid', created_at: '2026-10-09T10:26:25' };

function renderPayment() {
  return render(
    <I18nProvider locale="en">
      <MemoryRouter
        initialEntries={['/payment?bill=19']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <Routes>
          <Route path="/payment" element={<Payment />} />
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => {
  api.getBills.mockResolvedValue([BILL]);
  api.getCustomer.mockResolvedValue({ customer_id: 'CUST001', phone: '+250788123456' });
});

describe('Payment', () => {
  it('names the amount on the button and the number that pays', async () => {
    renderPayment();
    expect(await screen.findByRole('button', { name: 'Pay RWF 12,401' })).toBeEnabled();
    expect(screen.getByText(/078 812 3456/)).toBeInTheDocument();
  });

  it('shows Paid with the transaction id after paying', async () => {
    api.payBill.mockResolvedValue({ success: true, transaction_id: 'MOMO-000019-RW' });
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('heading', { name: 'Paid' })).toBeInTheDocument();
    expect(screen.getByText('You paid RWF 12,401.')).toBeInTheDocument();
    expect(screen.getByText('MOMO-000019-RW')).toHaveClass('code');
  });

  it('does not claim the household was not charged when the connection drops', async () => {
    api.payBill.mockRejectedValue(Object.assign(new Error('offline'), { kind: 'offline' }));
    renderPayment();
    const button = await screen.findByRole('button', { name: 'Pay RWF 12,401' });
    await act(async () => fireEvent.click(button));
    expect(screen.getByRole('alert')).toHaveTextContent('Check your bills before you try again');
    expect(screen.queryByText(/not been charged|not charged/i)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'See your bills' })).toBeInTheDocument();
  });

  it('shows an already-paid bill as paid, without a Pay button', async () => {
    api.getBills.mockResolvedValue([{ ...BILL, payment_status: 'paid' }]);
    renderPayment();
    expect(await screen.findByText('This bill is already paid.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Pay/ })).not.toBeInTheDocument();
  });
});
