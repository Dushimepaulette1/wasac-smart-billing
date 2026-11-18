import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SmsOutbox from '../../../src/pages/staff/SmsOutbox';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api } from '../../../src/api/client';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, smsOutbox: vi.fn() } };
});

afterEach(() => window.sessionStorage.clear());

it('shows Kinyarwanda delivery labels and preserves the original service response as details', async () => {
  const user = { username: 'admin', full_name: 'Admin', role: 'admin' };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
  vi.mocked(api.smsOutbox).mockResolvedValue([
    { id: 1, at: '2026-11-18T08:00:00', phone: '+250788123456', message: 'Kode yanyu ni 123456', status: 'sent' },
    { id: 2, at: '2026-11-18T08:01:00', phone: '+250788123456', message: 'Kode yanyu ni 654321', status: 'not sent (ReadTimeout)' },
  ]);
  render(
    <I18nProvider locale="rw">
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><SmsOutbox /></MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
  expect(await screen.findByText('Byoherejwe')).toBeInTheDocument();
  expect(screen.getByText('Ntibyoherejwe')).toBeInTheDocument();
  const summary = screen.getByText("Igisubizo cy'umwimerere cya serivisi yohereza ubutumwa");
  const details = summary.closest('details')!;
  expect(details).not.toHaveAttribute('open');
  expect(within(details).getByText('not sent (ReadTimeout)')).toBeInTheDocument();
  expect(screen.getByText('Kode yanyu ni 654321')).toBeInTheDocument();
});
