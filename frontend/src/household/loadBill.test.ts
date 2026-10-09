import loadBill from './loadBill';
import { api } from '../api/client';
import { cellsToDigits } from '../utils/reading';
import { makeBill, makeCalculatedBill, makeCustomer } from '../test/fixtures';

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/client')>();
  return {
    ...actual,
    api: { ...actual.api, getBills: vi.fn(), getCustomer: vi.fn(), calculateBill: vi.fn() },
  };
});

const BILLS = [
  makeBill({ bill_id: 19, consumption_m3: 20.5, amount_due: 12400.5, created_at: '2026-10-09T10:26:25' }),
  makeBill({ bill_id: 6, consumption_m3: 22, amount_due: 13587, payment_status: 'paid', created_at: '2026-09-09T09:38:11' }),
  makeBill({ bill_id: 5, consumption_m3: 20, amount_due: 12005, payment_status: 'paid', created_at: '2026-08-10T09:38:11' }),
];

beforeEach(() => {
  vi.mocked(api.getBills).mockResolvedValue(BILLS);
  vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ last_reading: 484.5 }));
  vi.mocked(api.calculateBill).mockResolvedValue(makeCalculatedBill());
});

describe('loadBill', () => {
  it('loads the newest bill with its meter reading and the one before', async () => {
    const data = await loadBill('CUST001', null);
    expect(data.bill.bill_id).toBe(19);
    expect(data.reading && cellsToDigits(data.reading)).toBe('00484500');
    expect(data.previousReading).toBeCloseTo(464);
    expect(data.periodStart).toBe('2026-09-09T09:38:11');
    expect(api.calculateBill).toHaveBeenCalledWith(20.5);
  });

  it('lists the tariff tiers that apply, in order, without empty ones', async () => {
    const data = await loadBill('CUST001', null);
    expect(data.tiers).toEqual([
      { units: 5, rate: 350, amount: 1750 },
      { units: 10, rate: 530, amount: 5300 },
      { units: 5.5, rate: 791, amount: 4350.5 },
    ]);
    expect(data.serviceCharge).toBe(1000);
  });

  it('has no meter reading for an older bill (the API does not keep one)', async () => {
    const data = await loadBill('CUST001', 6);
    expect(data.bill.bill_id).toBe(6);
    expect(data.reading).toBeNull();
    expect(data.previousReading).toBeNull();
  });

  it('lists usage oldest first, ending with this bill', async () => {
    const data = await loadBill('CUST001', 19);
    expect(data.history.map((b) => b.bill_id)).toEqual([5, 6, 19]);
  });

  it('reports a bill that does not exist as not found', async () => {
    await expect(loadBill('CUST001', 99)).rejects.toMatchObject({ kind: 'notFound' });
  });

  it('reports a household with no bills as not found', async () => {
    vi.mocked(api.getBills).mockResolvedValue([]);
    await expect(loadBill('CUST001', null)).rejects.toMatchObject({ kind: 'notFound' });
  });
});
