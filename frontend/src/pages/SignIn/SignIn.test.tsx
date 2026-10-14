import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SignIn from './SignIn';
import { I18nProvider } from '../../i18n/I18nProvider';
import { HouseholdProvider } from '../../household/session';
import { api, ApiError } from '../../api/client';
import { TEST_ACCOUNT } from '../../test/household';

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, api: { ...actual.api, requestCode: vi.fn(), verifyCode: vi.fn() } };
});

const renderSignIn = (path = '/sign-in') =>
  render(
    <I18nProvider locale="en">
      <HouseholdProvider>
        <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/sign-in" element={<SignIn />} />
            <Route path="/home" element={<p>Home page</p>} />
            <Route path="/history" element={<p>Bills page</p>} />
          </Routes>
        </MemoryRouter>
      </HouseholdProvider>
    </I18nProvider>,
  );

const session = (accounts = [TEST_ACCOUNT]) => ({
  access_token: 'tok',
  expires_at: Date.now() / 1000 + 3600,
  phone: '+250788123456',
  accounts,
});

afterEach(() => window.localStorage.clear());

describe('Household sign-in', () => {
  it('sends a code, shows a demo code, and signs in to where the household was going', async () => {
    vi.mocked(api.requestCode).mockResolvedValue({ phone: '+250788123456', expires_in: 600, resend_after: 60, demo_code: '482913' });
    vi.mocked(api.verifyCode).mockResolvedValue(session());
    renderSignIn('/sign-in?next=%2Fhistory');

    fireEvent.change(screen.getByLabelText('Your phone number'), { target: { value: '0788 123 456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    expect(await screen.findByText(/we have sent a 6-digit code/)).toHaveTextContent('078 812 3456');
    expect(screen.getByText('482913')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /New code in/ })).toBeDisabled();

    fireEvent.change(screen.getByLabelText('6-digit code'), { target: { value: '48 29 13' } });
    expect(screen.getByLabelText('6-digit code')).toHaveValue('482913');
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Bills page')).toBeInTheDocument();
    expect(api.verifyCode).toHaveBeenCalledWith('+250788123456', '482913');
  });

  it('says so when the code is wrong', async () => {
    vi.mocked(api.requestCode).mockResolvedValue({ phone: '+250788123456', expires_in: 600, resend_after: 60, demo_code: null });
    vi.mocked(api.verifyCode).mockRejectedValue(new ApiError('invalid', 400));
    renderSignIn();
    fireEvent.change(screen.getByLabelText('Your phone number'), { target: { value: '0788123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    fireEvent.change(await screen.findByLabelText('6-digit code'), { target: { value: '000000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText(/That code is not right/)).toBeInTheDocument();
  });

  it('asks which meter when the number has several', async () => {
    const second = { ...TEST_ACCOUNT, customer_id: 'CUST002', meter_id: 'MTR002', name: 'Shop on KN 5 Rd' };
    vi.mocked(api.requestCode).mockResolvedValue({ phone: '+250788123456', expires_in: 600, resend_after: 60, demo_code: null });
    vi.mocked(api.verifyCode).mockResolvedValue(session([TEST_ACCOUNT, second]));
    renderSignIn();
    fireEvent.change(screen.getByLabelText('Your phone number'), { target: { value: '0788123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a code' }));
    fireEvent.change(await screen.findByLabelText('6-digit code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    fireEvent.click(await screen.findByRole('button', { name: /Shop on KN 5 Rd/ }));
    expect(await screen.findByText('Home page')).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem('wasac.household') ?? '{}').customerId).toBe('CUST002');
  });
});
