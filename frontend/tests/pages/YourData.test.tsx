import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import HouseholdRoutes from '../../src/router/HouseholdRoutes';
import { I18nProvider } from '../../src/i18n/I18nProvider';

const renderPolicy = (path: string, locale: 'en' | 'rw' = 'en') =>
  render(
    <I18nProvider locale={locale}>
      <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <HouseholdRoutes />
      </MemoryRouter>
    </I18nProvider>,
  );

describe('Privacy policy', () => {
  it.each(['/privacy-policy', '/your-data'])('is public at %s, including the previous data-page URL', (path) => {
    renderPolicy(path);
    expect(screen.getByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('explains data, purposes, access, corrections and AI limitations', () => {
    renderPolicy('/privacy-policy');
    expect(screen.getByText(/Your name, phone number/)).toBeInTheDocument();
    expect(screen.getByText(/Meter photos you send/)).toBeInTheDocument();
    expect(screen.getByText(/Phone numbers identify linked accounts/)).toBeInTheDocument();
    expect(screen.getByText(/Project operators with server or database access/)).toBeInTheDocument();
    expect(screen.getByText(/default photo retention period is 90 days/)).toBeInTheDocument();
    expect(screen.getByText(/never refused because of this alone/)).toBeInTheDocument();
    expect(screen.getByText(/Confidence scores do not guarantee accuracy/)).toBeInTheDocument();
    expect(screen.getByText(/Check the digits against your meter/)).toBeInTheDocument();
    expect(screen.getByText(/Do not post phone numbers/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Contact the Mubazi project maintainer' })).toHaveAttribute(
      'href', 'https://github.com/Dushimepaulette1/wasac-smart-billing/issues/new',
    );
    expect(screen.getByText(/not an official WASAC service/)).toBeInTheDocument();
  });

  it('shows readable English fallback for untranslated Kinyarwanda policy text', () => {
    renderPolicy('/privacy-policy', 'rw');
    expect(screen.getByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeInTheDocument();
    expect(screen.getByText(/Confidence scores do not guarantee accuracy/)).toBeInTheDocument();
    expect(screen.queryByText(/TODO: translate/)).not.toBeInTheDocument();
  });
});
