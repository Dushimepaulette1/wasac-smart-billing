import { fireEvent, render, screen } from '@testing-library/react';
import { ApiError } from '../../src/api/client';
import { MemoryRouter } from 'react-router-dom';
import CustomerHome from '../../src/pages/CustomerHome/CustomerHome';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { api } from '../../src/api/client';
import { makeBill, makeCustomer, makeFlag, makeUsage } from '../support/fixtures';
import { TestHousehold } from '../support/household';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return {
    ...actual,
    api: {
      ...actual.api,
      getCustomer: vi.fn(),
      getBills: vi.fn(),
      getHouseholdFlags: vi.fn(),
      getUsage: vi.fn(),
      pushKey: vi.fn().mockRejectedValue(new Error('not set up')),
    },
  };
});

const renderHome = () =>
  render(
    <I18nProvider locale="en">
      <TestHousehold>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <CustomerHome />
        </MemoryRouter>
      </TestHousehold>
    </I18nProvider>,
  );

const recently = new Date(Date.now() - 3600 * 1000).toISOString().slice(0, 19);

beforeEach(() => {
  vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer());
  vi.mocked(api.getBills).mockResolvedValue([]);
  vi.mocked(api.getHouseholdFlags).mockResolvedValue([]);
  vi.mocked(api.getUsage).mockResolvedValue(makeUsage());
});

afterEach(() => window.localStorage.clear());

describe('CustomerHome', () => {
  it('when a bill is due, should lead with its amount and a pay button', async () => {
    vi.mocked(api.getBills).mockResolvedValue([makeBill({ bill_id: 23, amount_due: 12400, payment_status: 'unpaid' })]);
    renderHome();
    expect(await screen.findByRole('button', { name: 'Pay RWF 12,400' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('RWF 12,400');
  });

  it('when nothing is due, should ask for a reading', async () => {
    renderHome();
    expect(await screen.findByText('Read your meter to get your next bill.')).toBeInTheDocument();
  });

  it('when an officer accepted a reading lately, should say so until the household closes it', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      makeFlag({ id: 9, status: 'resolved', reading_status: 'valid', resolved_at: recently }),
    ]);
    const first = renderHome();
    expect(await screen.findByText('Your reading was accepted')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByText('Your reading was accepted')).not.toBeInTheDocument();

    first.unmount();
    renderHome();
    await screen.findByText('Read your meter to get your next bill.');
    expect(screen.queryByText('Your reading was accepted')).not.toBeInTheDocument();
  });

  it('when an officer rejected a reading, should ask for a new photo', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      makeFlag({ id: 10, status: 'resolved', reading_status: 'rejected', resolved_at: recently }),
    ]);
    renderHome();
    expect(await screen.findByText('Please read your meter again')).toBeInTheDocument();
  });

  it('when a new reading is waiting after a rejected one, should not ask for another', async () => {
    vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ reading_pending: true }));
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      makeFlag({ id: 10, status: 'resolved', reading_status: 'rejected', resolved_at: recently }),
    ]);
    renderHome();
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent("We're checking your reading");
    expect(screen.queryByText('Please read your meter again')).not.toBeInTheDocument();
  });

  it('should estimate the next bill from usual use, and say it is not a bill', async () => {
    renderHome();
    expect(await screen.findByText('About RWF 15,790 for about 20.0 m³')).toBeInTheDocument();
    expect(screen.getByText('An estimate from your usual use. It is not a bill.')).toBeInTheDocument();
  });

  it('when there is not enough history, should show no estimate', async () => {
    vi.mocked(api.getUsage).mockResolvedValue(makeUsage({ reason: 'not_enough_history', projected_m3: null, projected_amount: null }));
    renderHome();
    await screen.findByText('Read your meter to get your next bill.');
    expect(screen.queryByText('Your next bill')).not.toBeInTheDocument();
  });

  it('when a reading is being checked, should show no estimate', async () => {
    vi.mocked(api.getCustomer).mockResolvedValue(makeCustomer({ reading_pending: true }));
    renderHome();
    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByText('Your next bill')).not.toBeInTheDocument();
  });

  it("when checking with today's number, should update the estimate and warn about a leak", async () => {
    renderHome();
    fireEvent.click(await screen.findByRole('button', { name: "Check with today's number" }));
    vi.mocked(api.getUsage).mockResolvedValue(
      makeUsage({ projected_m3: 60, projected_amount: 58000, used_meter_now: true, used_so_far_m3: 10, leak_so_far: true }),
    );
    fireEvent.click(screen.getByRole('button', { name: 'Estimate' }));
    expect(await screen.findByText('About RWF 58,000 for about 60.0 m³')).toBeInTheDocument();
    expect(screen.getByText('Since your last reading, you have used much more water than usual')).toBeInTheDocument();
    expect(api.getUsage).toHaveBeenLastCalledWith(expect.any(String), 484.5);
  });

  it("when today's number is lower than the last reading, should say so", async () => {
    renderHome();
    fireEvent.click(await screen.findByRole('button', { name: "Check with today's number" }));
    vi.mocked(api.getUsage).mockRejectedValue(new ApiError('invalid', 422, 'lower'));
    fireEvent.click(screen.getByRole('button', { name: 'Estimate' }));
    expect(await screen.findByText('This number is lower than your last reading. Check the digits.')).toBeInTheDocument();
    // The counter is still there with the number, ready to fix and try again.
    expect(screen.getByRole('button', { name: 'Estimate' })).toBeEnabled();
  });

  it('when the estimate fails to load, should keep the number and let the household try again', async () => {
    renderHome();
    fireEvent.click(await screen.findByRole('button', { name: "Check with today's number" }));
    vi.mocked(api.getUsage).mockRejectedValueOnce(new ApiError('offline'));
    fireEvent.click(screen.getByRole('button', { name: 'Estimate' }));
    expect(await screen.findByText(/Your number is kept. Try again./)).toBeInTheDocument();
    vi.mocked(api.getUsage).mockResolvedValueOnce(makeUsage({ projected_amount: 17000, used_meter_now: true }));
    fireEvent.click(screen.getByRole('button', { name: 'Estimate' }));
    expect(await screen.findByText('About RWF 17,000 for about 20.0 m³')).toBeInTheDocument();
  });

  it('when the last bill looks like a leak, should say how much above usual and what to check', async () => {
    vi.mocked(api.getUsage).mockResolvedValue(makeUsage({ leak_warning: true, leak_reading_id: 40, percent_above_usual: 67 }));
    renderHome();
    expect(await screen.findByText('Your last bill was about 67% above your usual use')).toBeInTheDocument();
    expect(screen.getByText('a toilet that keeps running')).toBeInTheDocument();
    expect(screen.getByText('Need help? Call WASAC on 1580.')).toBeInTheDocument();
  });

  it('when a high-use reading is being checked, should show the leak notice with a link to the message', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([makeFlag({ anomaly_type: 'SPIKE', status: 'open' })]);
    renderHome();
    expect(await screen.findByText('Your water use is higher than usual')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Read the message' })).toBeInTheDocument();
  });
});
