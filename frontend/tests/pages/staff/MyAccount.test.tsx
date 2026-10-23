import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import MyAccount from '../../../src/pages/staff/MyAccount';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider, RequireStaff } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, changePassword: vi.fn(), reviewQueue: vi.fn().mockResolvedValue([]) } };
});

const user = { username: 'new.officer', full_name: 'New Officer', role: 'officer' };

function signIn(mustChange: boolean, token = 'old') {
  window.sessionStorage.setItem(
    'wasac.staff',
    JSON.stringify({ token, expiresAt: Date.now() / 1000 + 3600, user: { ...user, must_change_password: mustChange } }),
  );
}

function renderAt(path: string) {
  return render(
    <I18nProvider locale="en">
      <AuthProvider>
        <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/staff/review" element={<RequireStaff><p>Review page</p></RequireStaff>} />
            <Route path="/staff/account" element={<RequireStaff><MyAccount /></RequireStaff>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
}

afterEach(() => window.sessionStorage.clear());

describe('MyAccount', () => {
  it('when signed in with a temporary password, should open My account instead of other pages', () => {
    signIn(true);
    renderAt('/staff/review');
    expect(screen.queryByText('Review page')).not.toBeInTheDocument();
    expect(screen.getByText(/choose your own password first/i)).toBeInTheDocument();
  });

  it('when the password is changed, should keep the session with the new token and open the dashboard', async () => {
    signIn(true);
    vi.mocked(api.changePassword).mockResolvedValue({
      access_token: 'new', token_type: 'bearer', expires_at: Date.now() / 1000 + 3600,
      user: { ...user, must_change_password: false },
    });
    renderAt('/staff/account');
    fireEvent.change(screen.getByLabelText(/current password/i), { target: { value: 'k7mq-x3vd-9tpa' } });
    fireEvent.change(screen.getByLabelText(/^new password/i), { target: { value: 'my own password' } });
    fireEvent.change(screen.getByLabelText(/repeat the new password/i), { target: { value: 'my own password' } });
    fireEvent.click(screen.getByRole('button', { name: /change password/i }));

    expect(await screen.findByText(/password changed/i)).toBeInTheDocument();
    expect(api.changePassword).toHaveBeenCalledWith('k7mq-x3vd-9tpa', 'my own password');
    const saved = JSON.parse(window.sessionStorage.getItem('wasac.staff') ?? '{}');
    expect(saved.token).toBe('new');
    expect(saved.user.must_change_password).toBe(false);
    expect(screen.queryByText(/choose your own password first/i)).not.toBeInTheDocument();
  });

  it('when the password is not temporary, should open every page', () => {
    signIn(false);
    renderAt('/staff/review');
    expect(screen.getByText('Review page')).toBeInTheDocument();
  });
});
