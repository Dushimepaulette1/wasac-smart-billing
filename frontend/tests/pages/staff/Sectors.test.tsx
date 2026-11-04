import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sectors from '../../../src/pages/staff/Sectors';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AuthProvider } from '../../../src/staff/auth';
import { api, ApiError } from '../../../src/api/client';
import { makeSector } from '../../support/fixtures';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, listSectors: vi.fn() } };
});

function renderPage() {
  const user = { username: 'officer1', full_name: 'Officer One', role: 'officer' };
  window.sessionStorage.setItem('wasac.staff', JSON.stringify({ token: 't', expiresAt: Date.now() / 1000 + 3600, user }));
  return render(
    <I18nProvider locale="en">
      <AuthProvider>
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Sectors />
        </MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
}

afterEach(() => window.sessionStorage.clear());

describe('Sectors', () => {
  it('should list sectors in the order the server sends them, the urgent ones marked', async () => {
    vi.mocked(api.listSectors).mockResolvedValue([
      makeSector({
        sector: 'Kacyiru', held_readings: 1, possible_leaks: 1, owed: 15790,
        attention: [
          { customer_id: 'C1', name: 'Uwase Home', meter_id: 'KGL-20001', held: true, possible_leak: false, owed: 0 },
          { customer_id: 'C2', name: 'Mugisha Home', meter_id: 'KGL-20002', held: false, possible_leak: true, owed: 15790 },
        ],
      }),
      makeSector({ sector: 'Remera' }),
    ]);
    renderPage();
    const cards = await screen.findAllByRole('listitem', { name: /Kacyiru|Remera/ });
    expect(cards.map((c) => c.getAttribute('aria-label'))).toEqual(['Kacyiru', 'Remera']);
    const [kacyiru, remera] = cards as [HTMLElement, HTMLElement];
    expect(kacyiru).toHaveClass('panel-ink');
    expect(remera).not.toHaveClass('panel-ink');
    expect(within(kacyiru).getByText('RWF 15,790')).toBeInTheDocument();
    expect(within(remera).queryByText(/Show households/)).not.toBeInTheDocument();
  });

  it('when a sector is opened, should list its households and link held readings to the review queue', async () => {
    vi.mocked(api.listSectors).mockResolvedValue([
      makeSector({
        sector: 'Kacyiru', held_readings: 1,
        attention: [{ customer_id: 'C1', name: 'Uwase Home', meter_id: 'KGL-20001', held: true, possible_leak: false, owed: 0 }],
      }),
    ]);
    renderPage();
    fireEvent.click(await screen.findByText('Show households needing attention (1)'));
    expect(screen.getByRole('link', { name: 'Uwase Home' })).toHaveAttribute('href', '/staff/review');
    expect(screen.getByText('Reading to check')).toBeInTheDocument();
  });

  it('when households have no sector or too few readings, should say so', async () => {
    vi.mocked(api.listSectors).mockResolvedValue([makeSector({ sector: '', usual_monthly_m3: null })]);
    renderPage();
    expect(await screen.findByText('No sector')).toBeInTheDocument();
    expect(screen.getByText('Not enough readings')).toBeInTheDocument();
  });

  it('when the sectors fail to load, should offer to try again', async () => {
    vi.mocked(api.listSectors).mockRejectedValue(new ApiError('offline'));
    renderPage();
    expect(await screen.findByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });
});
