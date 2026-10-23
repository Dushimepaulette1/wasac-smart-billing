import { fireEvent, render, screen } from '@testing-library/react';
import MeterCorrection from '../../../src/pages/staff/MeterCorrection';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { api, ApiError } from '../../../src/api/client';
import { makeCustomer } from '../../support/fixtures';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, correctMeter: vi.fn() } };
});

const household = { ...makeCustomer({ customer_id: 'DEMO-CUST-001', meter_id: 'DEMO-MTR-001', name: 'DEMO Household 001', last_reading: 998.332 }), unpaidCount: 0, unpaidAmount: 0 };

function renderPanel(onCorrected = vi.fn()) {
  render(
    <I18nProvider locale="en">
      <MeterCorrection households={[household]} onCorrected={onCorrected} />
    </I18nProvider>,
  );
  return onCorrected;
}

function fill(reading: string, reason: string) {
  fireEvent.change(screen.getByLabelText('Household'), { target: { value: 'DEMO-CUST-001' } });
  fireEvent.change(screen.getByLabelText('What the meter shows now (m³)'), { target: { value: reading } });
  fireEvent.change(screen.getByLabelText('Reason'), { target: { value: reason } });
  fireEvent.click(screen.getByRole('button', { name: 'Save the correction' }));
}

describe('MeterCorrection', () => {
  it('when a household is chosen, should show what is on record now', () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText('Household'), { target: { value: 'DEMO-CUST-001' } });
    expect(screen.getByText('On record now: 998.332 m³')).toBeInTheDocument();
  });

  it('when the form is incomplete, should say what is missing and not send it', async () => {
    renderPanel();
    fill('355.036', '');
    expect(await screen.findByText(/then type the reading/)).toBeInTheDocument();
    expect(api.correctMeter).not.toHaveBeenCalled();
  });

  it('when the correction is saved, should confirm it and refresh the list', async () => {
    vi.mocked(api.correctMeter).mockResolvedValue(makeCustomer({ meter_id: 'DEMO-MTR-001', last_reading: 355.036 }));
    const onCorrected = renderPanel();
    fill('355,036', 'Meter replaced');
    expect(await screen.findByText(/DEMO-MTR-001 now reads 355.036 m³/)).toBeInTheDocument();
    expect(api.correctMeter).toHaveBeenCalledWith('DEMO-CUST-001', 355.036, 'Meter replaced');
    expect(onCorrected).toHaveBeenCalled();
  });

  it('when a reading is waiting for review, should ask to decide on it first', async () => {
    vi.mocked(api.correctMeter).mockRejectedValue(new ApiError('conflict', 409));
    renderPanel();
    fill('355.036', 'Meter replaced');
    expect(await screen.findByText(/waiting in the review queue/)).toBeInTheDocument();
  });
});
