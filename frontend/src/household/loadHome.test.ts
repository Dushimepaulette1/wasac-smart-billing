import loadHome from './loadHome';
import { api } from '../api/client';
import type { AnomalyType, FlagStatus } from '../api/types';
import { makeBill, makeCustomer, makeFlag } from '../test/fixtures';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    api: { ...actual.api, getCustomer: vi.fn(), getBills: vi.fn(), getHouseholdFlags: vi.fn() },
  };
});

const flag = (anomaly_type: AnomalyType, status: FlagStatus = 'open', requires_staff_review = true) =>
  makeFlag({ anomaly_type, status, requires_staff_review });

beforeEach(() => {
  vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer());
  vi.mocked(api.getBills).mockResolvedValue([
    makeBill({ bill_id: 23, payment_status: 'unpaid' }),
    makeBill({ bill_id: 22, payment_status: 'paid' }),
  ]);
  vi.mocked(api.getHouseholdFlags).mockResolvedValue([]);
});

describe('loadHome', () => {
  it('returns the newest bill so home can offer to pay it', async () => {
    const home = await loadHome('CUST001', 'MTR001');
    expect(home.newestBill?.bill_id).toBe(23);
    expect(home.checking).toBe(false);
    expect(home.highUse).toBe(false);
  });

  it('notices readings being checked and high use, ignoring resolved flags', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag('MISREAD_SUSPECTED'), flag('SPIKE', 'resolved')]);
    let home = await loadHome('CUST001', 'MTR001');
    expect(home.checking).toBe(true);
    expect(home.highUse).toBe(false);

    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag('SUSTAINED_HIGH', 'open', false)]);
    home = await loadHome('CUST001', 'MTR001');
    expect(home.checking).toBe(false);
    expect(home.highUse).toBe(true);
  });

  it('still loads when the flags request fails', async () => {
    vi.mocked(api.getHouseholdFlags).mockRejectedValue(new Error('offline'));
    const home = await loadHome('CUST001', 'MTR001');
    expect(home.customer.name).toBe('Uwimana Jean Pierre');
    expect(home.checking).toBe(false);
  });
});
