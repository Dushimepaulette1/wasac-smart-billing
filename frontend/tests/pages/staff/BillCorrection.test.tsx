import { act, fireEvent, render, screen } from '@testing-library/react';
import BillCorrection from '../../../src/pages/staff/BillCorrection';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';
import type { BillCorrection as Correction, BillSummary } from '../../../src/api/types';
import { makeCustomer } from '../../support/fixtures';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, staffBills: vi.fn(), correctBill: vi.fn(), billCorrections: vi.fn(), decideBillCorrection: vi.fn() } };
});

const household = { ...makeCustomer({ customer_id: 'C1', meter_id: 'M1', name: 'House One' }), unpaidCount: 0, unpaidAmount: 0 };
const bill = { bill_id: 7, reading_id: 70, consumption_m3: 31.46, amount_due: 21375, charges: 21375, payment_status: 'unpaid', created_at: '2026-09-01T08:00:00' } as BillSummary;
const line = { bill_id: 7, consumption_before: 31.46, consumption_after: 21.46, amount_before: 21375, amount_after: 13159.86, amount_delta: -8215.14, tariff_version: 'v1-provisional' };
const correction = (extra: Partial<Correction>): Correction => ({
  id: 3, status: 'preview', customer_id: 'C1', customer_name: 'House One', reading_id: 70, value_before_m3: 431.46,
  corrected_value_m3: 421.46, reason: 'Read again on site', requested_by: 'sup1', decided_by: null, decision_reason: null,
  needs_approval: false, net_delta: -8215.14, adjustments: [line], ...extra,
});

function renderPanel(username = 'sup1') {
  const user = { username, full_name: 'S', role: 'supervisor' };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
  render(<I18nProvider locale="en"><AuthProvider><BillCorrection households={[household]} onCorrected={vi.fn()} /></AuthProvider></I18nProvider>);
}

async function fill() {
  fireEvent.change(screen.getByLabelText('Household'), { target: { value: 'C1' } });
  await screen.findByRole('option', { name: /21,375/ });
  fireEvent.change(screen.getByLabelText('Bill'), { target: { value: '70' } });
  fireEvent.change(screen.getByLabelText('The right reading (m³)'), { target: { value: '421.460' } });
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: 'Read again on site' } });
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Show the effect' })); });
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.staffBills).mockResolvedValue([bill]);
  vi.mocked(api.billCorrections).mockResolvedValue([]);
});
afterEach(() => window.sessionStorage.clear());

describe('BillCorrection', () => {
  it('when previewing, should show the effect on each bill and store nothing', async () => {
    vi.mocked(api.correctBill).mockResolvedValue(correction({}));
    renderPanel();
    await fill();
    expect(await screen.findByText(/Bill 7: 31.460 → 21.460 m³/)).toBeInTheDocument();
    expect(vi.mocked(api.correctBill).mock.calls[0]?.[2].apply).toBe(false);
  });

  it('when it charges more, should say approval is needed and keep the same request key', async () => {
    vi.mocked(api.correctBill).mockResolvedValue(correction({ needs_approval: true, net_delta: 500 }));
    renderPanel();
    await fill();
    vi.mocked(api.correctBill).mockResolvedValue(correction({ status: 'awaiting_approval' }));
    await act(async () => { fireEvent.click(await screen.findByRole('button', { name: 'Ask for approval' })); });
    expect(await screen.findByText(/must approve it\./)).toBeInTheDocument();
    const [first, second] = vi.mocked(api.correctBill).mock.calls;
    expect(second?.[2].apply).toBe(true);
    expect(second?.[2].request_key).toBe(first?.[2].request_key);
  });

  it('when someone else asked for it, should offer approve; when you did, should not', async () => {
    vi.mocked(api.billCorrections).mockResolvedValue([correction({ status: 'awaiting_approval', requested_by: 'sup1' })]);
    renderPanel('sup2');
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeInTheDocument();
  });

  it('when you asked for it yourself, should not offer approve', async () => {
    vi.mocked(api.billCorrections).mockResolvedValue([correction({ status: 'awaiting_approval', requested_by: 'sup1' })]);
    renderPanel('sup1');
    expect(await screen.findByText('Someone else must decide a correction you asked for.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });
});
