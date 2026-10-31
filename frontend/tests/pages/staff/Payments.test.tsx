import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Payments from '../../../src/pages/staff/Payments';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';
import type { PaymentToCheck } from '../../../src/api/types';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, paymentsToCheck: vi.fn(), recheckPayment: vi.fn(), reconcilePayment: vi.fn(), markPaymentReviewed: vi.fn() } };
});

const row = (id: number, kind: PaymentToCheck['kind'], name: string): PaymentToCheck => ({
  kind, id, bill_id: 10 + id, customer_id: `CUST-${id}`, customer_name: name, meter_id: `MTR-${id}`,
  amount: 6460, transaction_id: `MP${id}`, created_at: '2026-10-20T08:00:00', submitted_at: '2026-10-20T08:05:00',
});

function renderPage(role = 'officer') {
  const user = { username: 'officer1', full_name: 'Officer One', role };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
  return render(
    <I18nProvider locale="en">
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Payments />
        </MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
}

afterEach(() => window.sessionStorage.clear());

describe('Payments', () => {
  it('when a bill was paid twice, should say so and offer no confirm or decline', async () => {
    vi.mocked(api.paymentsToCheck).mockResolvedValue([row(1, 'momo_pay_check', 'Waiting House'), row(2, 'paid_twice', 'Twice House')]);
    renderPage();
    expect(await screen.findByText(/Paid twice/)).toBeInTheDocument();
    // Only the MoMo Pay payment waiting for a check can be confirmed.
    expect(screen.getAllByRole('button', { name: 'Found: confirm' })).toHaveLength(1);
  });

  it('when an MTN payment is stuck, an officer can only ask MTN again', async () => {
    vi.mocked(api.paymentsToCheck).mockResolvedValue([row(3, 'needs_reconciliation', 'Stuck House')]);
    vi.mocked(api.recheckPayment).mockResolvedValue({ status: 'pending' } as Awaited<ReturnType<typeof api.recheckPayment>>);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Ask MTN again' }));
    expect(await screen.findByText('MTN has still not settled it.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /records show/ })).not.toBeInTheDocument();
  });

  it('when a supervisor closes a stuck payment, should need evidence and send it', async () => {
    vi.mocked(api.paymentsToCheck).mockResolvedValue([row(3, 'needs_reconciliation', 'Stuck House')]);
    vi.mocked(api.reconcilePayment).mockResolvedValue({ status: 'failed' } as Awaited<ReturnType<typeof api.reconcilePayment>>);
    renderPage('supervisor');
    fireEvent.click(await screen.findByRole('button', { name: "MTN's records show no charge" }));
    const save = screen.getByRole('button', { name: 'Save the decision' });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/What you checked/), { target: { value: 'Partner portal, nothing found' } });
    await act(async () => { fireEvent.click(save); });
    expect(api.reconcilePayment).toHaveBeenCalledWith(3, { outcome: 'failed', evidence: 'Partner portal, nothing found' });
  });

  it('when a double payment was looked at, should leave the list', async () => {
    vi.mocked(api.paymentsToCheck).mockResolvedValue([row(2, 'paid_twice', 'Twice House')]);
    vi.mocked(api.markPaymentReviewed).mockResolvedValue({} as Awaited<ReturnType<typeof api.markPaymentReviewed>>);
    renderPage();
    const reviewed = await screen.findByRole('button', { name: 'Mark as reviewed' });
    await act(async () => { fireEvent.click(reviewed); });
    expect(screen.queryByText('Twice House')).not.toBeInTheDocument();
  });
});
