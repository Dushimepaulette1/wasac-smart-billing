import loadBill from '../../src/household/loadBill';
import { api } from '../../src/api/client';
import { cellsToDigits } from '../../src/utils/reading';
import { makeBill, makeCalculatedBill, makeCustomer, makeUsage } from '../support/fixtures';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return {
    ...actual,
    api: { ...actual.api, getBills: vi.fn(), getCustomer: vi.fn(), calculateBill: vi.fn(), getUsage: vi.fn() },
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
  vi.mocked(api.getUsage).mockResolvedValue(makeUsage());
});

describe('loadBill', () => {
  it('when loading the newest bill, should include its meter reading and the one before', async () => {
    const data = await loadBill('CUST001', null);
    expect(data.bill.bill_id).toBe(19);
    expect(data.reading && cellsToDigits(data.reading.cells)).toBe('00484500');
    expect(data.reading?.previous).toBeCloseTo(464);
    expect(data.periodStart).toBe('2026-09-09T09:38:11');
    expect(api.calculateBill).toHaveBeenCalledWith(20.5, undefined) // the bill's own tariff version, none on this fixture;
  });

  it('when showing the tariff, should list the tiers that apply, in order, without empty ones', async () => {
    const data = await loadBill('CUST001', null);
    expect(data.tiers).toEqual([
      { units: 5, rate: 350, amount: 1750 },
      { units: 10, rate: 530, amount: 5300 },
      { units: 5.5, rate: 791, amount: 4350.5 },
    ]);
    expect(data.serviceCharge).toBe(1000);
    expect(data.vat).toBe(0);
  });

  it('when the bill is an older one, should have no meter reading (the API keeps none)', async () => {
    const data = await loadBill('CUST001', 6);
    expect(data.bill.bill_id).toBe(6);
    expect(data.reading).toBeNull();
  });

  it('when showing usage, should list it oldest first, ending with this bill', async () => {
    const data = await loadBill('CUST001', 19);
    expect(data.history.map((b) => b.bill_id)).toEqual([5, 6, 19]);
  });

  it('when the bill does not exist, should report not found', async () => {
    await expect(loadBill('CUST001', 99)).rejects.toMatchObject({ kind: 'notFound' });
  });

  it('when the household has no bills, should report not found', async () => {
    vi.mocked(api.getBills).mockResolvedValue([]);
    await expect(loadBill('CUST001', null)).rejects.toMatchObject({ kind: 'notFound' });
  });

  it('when the newest period looks like a leak, should give the percent on that bill only', async () => {
    const bills = [makeBill({ bill_id: 19, reading_id: 40 }), makeBill({ bill_id: 6, reading_id: 39 })];
    vi.mocked(api.getBills).mockResolvedValue(bills);
    vi.mocked(api.getUsage).mockResolvedValue(makeUsage({ leak_warning: true, leak_reading_id: 40, percent_above_usual: 67 }));
    expect((await loadBill('CUST001', 19)).leakPercent).toBe(67);
    expect((await loadBill('CUST001', 6)).leakPercent).toBeNull();
  });

  it('when the usage does not load, should still show the bill', async () => {
    vi.mocked(api.getUsage).mockRejectedValue(new Error('offline'));
    expect((await loadBill('CUST001', null)).leakPercent).toBeNull();
  });
});
