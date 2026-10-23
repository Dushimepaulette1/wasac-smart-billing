import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CustomerHome from '../../src/pages/CustomerHome/CustomerHome';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { api } from '../../src/api/client';
import { makeBill, makeCustomer, makeFlag } from '../support/fixtures';
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
});
