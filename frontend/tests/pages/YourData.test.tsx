import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import YourData from '../../src/pages/YourData/YourData';
import { I18nProvider } from '../../src/i18n/I18nProvider';

describe('YourData', () => {
  it('when opened, should say what is kept, who sees it and how long photos stay', () => {
    render(
      <I18nProvider locale="en">
        <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <YourData />
        </MemoryRouter>
      </I18nProvider>,
    );
    expect(screen.getByRole('heading', { level: 1, name: 'Your data' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Who can see it' })).toBeInTheDocument();
    expect(screen.getByText(/deleted after 90 days/)).toBeInTheDocument();
    expect(screen.getByText(/never refused because of this alone/)).toBeInTheDocument();
    expect(screen.getByText(/not an official WASAC service/)).toBeInTheDocument();
  });
});
