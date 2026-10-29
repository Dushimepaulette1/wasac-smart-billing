import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Payments from '../../../src/pages/staff/Payments';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';
import type { PaymentToCheck } from '../../../src/api/types';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, paymentsToCheck: vi.fn() } };
});

const row = (id: number, kind: PaymentToCheck['kind'], name: string): PaymentToCheck => ({
  kind, id, bill_id: 10 + id, customer_id: `CUST-${id}`, customer_name: name, meter_id: `MTR-${id}`,
  amount: 6460, transaction_id: `MP${id}`, created_at: '2026-10-20T08:00:00', submitted_at: '2026-10-20T08:05:00',
});

function renderPage() {
  const user = { username: 'officer1', full_name: 'Officer One', role: 'officer' };
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
});
