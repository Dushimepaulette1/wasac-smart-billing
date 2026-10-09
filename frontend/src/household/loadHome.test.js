import loadHome from './loadHome';
import { api } from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, api: { getCustomer: vi.fn(), getBills: vi.fn(), getHouseholdFlags: vi.fn() } };
});

const flag = (anomaly_type, status = 'open', requires_staff_review = true) => ({ anomaly_type, status, requires_staff_review });

beforeEach(() => {
  api.getCustomer.mockResolvedValue({ customer_id: 'CUST001', name: 'Uwimana Jean Pierre' });
  api.getBills.mockResolvedValue([{ bill_id: 23, payment_status: 'unpaid' }, { bill_id: 22, payment_status: 'paid' }]);
  api.getHouseholdFlags.mockResolvedValue([]);
});

describe('loadHome', () => {
  it('returns the newest bill so home can offer to pay it', async () => {
    const home = await loadHome('CUST001', 'MTR001');
    expect(home.newestBill.bill_id).toBe(23);
    expect(home.checking).toBe(false);
    expect(home.highUse).toBe(false);
  });

  it('notices readings being checked and high use, ignoring resolved flags', async () => {
    api.getHouseholdFlags.mockResolvedValue([
      flag('MISREAD_SUSPECTED'),
      flag('SPIKE', 'resolved'),
    ]);
    let home = await loadHome('CUST001', 'MTR001');
    expect(home.checking).toBe(true);
    expect(home.highUse).toBe(false);

    api.getHouseholdFlags.mockResolvedValue([flag('SUSTAINED_HIGH', 'open', false)]);
    home = await loadHome('CUST001', 'MTR001');
    expect(home.checking).toBe(false);
    expect(home.highUse).toBe(true);
  });

  it('still loads when the flags request fails', async () => {
    api.getHouseholdFlags.mockRejectedValue(new Error('offline'));
    const home = await loadHome('CUST001', 'MTR001');
    expect(home.customer.name).toBe('Uwimana Jean Pierre');
    expect(home.checking).toBe(false);
  });
});
