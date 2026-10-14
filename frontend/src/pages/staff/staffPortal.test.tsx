import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Accounts from './Accounts';
import Activity from './Activity';
import { I18nProvider } from '../../i18n/I18nProvider';
import { AuthProvider, hasRole } from '../../staff/auth';
import { api } from '../../api/client';
import type { StaffAccount, StaffRole } from '../../api/types';

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return {
    ...actual,
    api: {
      ...actual.api,
      reviewQueue: vi.fn().mockResolvedValue([]),
      activity: vi.fn(),
      staffAccounts: vi.fn(),
      createStaffAccount: vi.fn(),
    },
  };
});

const account = (username: string, role: StaffRole, extra: Partial<StaffAccount> = {}): StaffAccount => ({
  username,
  full_name: username === 'admin1' ? 'Admin One' : 'Uwase Jeanne',
  role,
  is_active: true,
  created_at: '2026-10-01T08:00:00',
  last_sign_in: null,
  ...extra,
});

function signInAs(role: StaffRole) {
  const user = { username: `${role}1`, full_name: role === 'admin' ? 'Admin One' : 'Officer One', role };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
}

const renderPage = (page: JSX.Element) =>
  render(
    <I18nProvider locale="en">
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{page}</MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );

afterEach(() => window.sessionStorage.clear());

describe('roles', () => {
  it('rank officer < supervisor < admin', () => {
    const user = (role: string) => ({ username: 'x', full_name: 'X', role });
    expect(hasRole(user('admin'), 'supervisor')).toBe(true);
    expect(hasRole(user('supervisor'), 'admin')).toBe(false);
    expect(hasRole(user('officer'), 'officer')).toBe(true);
    expect(hasRole(user('unknown'), 'supervisor')).toBe(false);
    expect(hasRole(null, 'officer')).toBe(false);
  });
});

describe('Activity', () => {
  it('shows an officer their own rows, without the person filter or the accounts page', async () => {
    signInAs('officer');
    vi.mocked(api.activity).mockResolvedValue([
      { id: 1, at: '2026-10-14T07:30:00', username: 'officer1', action: 'reject', target: 'flag 7', detail: 'DEMO-MTR-001 SPIKE' },
    ]);
    renderPage(<Activity />);
    expect(await screen.findByText('Rejected a reading')).toBeInTheDocument();
    expect(screen.getByText('flag 7 · DEMO-MTR-001 SPIKE')).toBeInTheDocument();
    expect(screen.queryByLabelText('Who')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Staff accounts/ })).not.toBeInTheDocument();
  });

  it('lets a supervisor narrow it to one person', async () => {
    signInAs('supervisor');
    vi.mocked(api.activity).mockResolvedValue([]);
    renderPage(<Activity />);
    expect(await screen.findByText('Nothing recorded yet.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Who'), { target: { value: 'officer1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Show' }));
    expect(api.activity).toHaveBeenLastCalledWith({ username: 'officer1', action: undefined });
  });
});

describe('Staff accounts', () => {
  it('adds a person and shows their temporary password once', async () => {
    signInAs('admin');
    vi.mocked(api.staffAccounts).mockResolvedValue([account('admin1', 'admin')]);
    vi.mocked(api.createStaffAccount).mockResolvedValue({
      account: account('u.jeanne', 'officer'),
      temporary_password: 'k7mq-x3vd-9tpa',
    });
    renderPage(<Accounts />);
    const table = await screen.findByRole('table');
    const row = within(table).getByText('Admin One').closest('tr') as HTMLElement;
    expect(within(row).getByText('(you)')).toBeInTheDocument();
    expect(within(row).getByRole('combobox')).toBeDisabled(); // cannot change own role
    expect(within(row).queryByRole('button', { name: 'Turn off' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Add account' }));
    expect(await screen.findByText(/Enter the full name and a username/)).toBeInTheDocument();
    expect(api.createStaffAccount).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Uwase Jeanne' } });
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'U.Jeanne' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add account' }));
    expect(api.createStaffAccount).toHaveBeenCalledWith({ username: 'u.jeanne', full_name: 'Uwase Jeanne', role: 'officer' });
    expect(await screen.findByText('k7mq-x3vd-9tpa')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Done' }));
    expect(screen.queryByText('k7mq-x3vd-9tpa')).not.toBeInTheDocument();
  });
});
