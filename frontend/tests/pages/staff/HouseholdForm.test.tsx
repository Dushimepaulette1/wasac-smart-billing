import { fireEvent, render, screen } from '@testing-library/react';
import HouseholdForm, { isRwandanMobile } from '../../../src/pages/staff/HouseholdForm';
import HouseholdImport from '../../../src/pages/staff/HouseholdImport';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { api, ApiError } from '../../../src/api/client';
import { makeCustomer } from '../../support/fixtures';

vi.mock('../../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../src/api/client')>();
  return { ...actual, api: { ...actual.api, addHousehold: vi.fn(), editHousehold: vi.fn(), importHouseholds: vi.fn() } };
});

function renderForm(props: Partial<Parameters<typeof HouseholdForm>[0]> = {}) {
  const onSaved = vi.fn();
  render(
    <I18nProvider locale="en">
      <HouseholdForm onSaved={onSaved} onCancel={vi.fn()} {...props} />
    </I18nProvider>,
  );
  return onSaved;
}

const type = (label: string | RegExp, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe('HouseholdForm', () => {
  it('should accept the ways people write a Rwandan mobile number', () => {
    expect(['078 123 4567', '+250 788-123-456', '788123456', '250722000444'].every(isRwandanMobile)).toBe(true);
    expect(['12345', '0612345678', 'abc'].some(isRwandanMobile)).toBe(false);
  });

  it('when fields are wrong, should say what to fix next to each one and send nothing', async () => {
    renderForm();
    type('Name', 'A');
    type('Phone number', '12345');
    type('Meter number', 'DEMO-1');
    fireEvent.click(screen.getByRole('button', { name: 'Add household' }));
    expect(await screen.findByText(/Enter a Rwandan mobile number/)).toBeInTheDocument();
    expect(screen.getByText(/kept for test households/)).toBeInTheDocument();
    expect(screen.getByLabelText('Phone number')).toHaveAttribute('aria-invalid', 'true');
    expect(api.addHousehold).not.toHaveBeenCalled();
  });

  it('when a household is added, should send the cleaned fields', async () => {
    const saved = makeCustomer({ name: 'Mukamana Alice', meter_id: 'KGL-30001' });
    vi.mocked(api.addHousehold).mockResolvedValue(saved);
    const onSaved = renderForm();
    type('Name', ' Mukamana Alice ');
    type('Phone number', '0788 555 123');
    type('Meter number', 'kgl-30001');
    type('Sector', 'Remera');
    type(/First reading/, '120,5');
    fireEvent.click(screen.getByRole('button', { name: 'Add household' }));
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved));
    expect(api.addHousehold).toHaveBeenCalledWith({
      name: 'Mukamana Alice', phone: '0788 555 123', meter_id: 'KGL-30001', sector: 'Remera',
      serial_number: undefined, first_reading: '120.5', customer_id: undefined,
    });
  });

  it('when the meter is already registered, should say so', async () => {
    vi.mocked(api.addHousehold).mockRejectedValue(new ApiError('conflict', 409));
    renderForm();
    type('Name', 'Mukamana Alice');
    type('Phone number', '0788555123');
    type('Meter number', 'KGL-30001');
    type('Sector', 'Remera');
    fireEvent.click(screen.getByRole('button', { name: 'Add household' }));
    expect(await screen.findByText(/already registered/)).toBeInTheDocument();
  });

  it('when editing, should not offer to change the meter number', async () => {
    const household = makeCustomer({ customer_id: 'C-1', meter_id: 'KGL-30001', phone: '+250788555123' });
    vi.mocked(api.editHousehold).mockResolvedValue(household);
    renderForm({ household });
    expect(screen.queryByLabelText('Meter number')).not.toBeInTheDocument();
    type('Phone number', '0722 000 444');
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    await vi.waitFor(() => expect(api.editHousehold).toHaveBeenCalled());
    expect(vi.mocked(api.editHousehold).mock.calls[0]).toEqual(['C-1', expect.objectContaining({ phone: '0722 000 444' })]);
  });
});

describe('HouseholdImport', () => {
  const upload = (text: string) => {
    const file = new File([text], 'customers.csv', { type: 'text/csv' });
    fireEvent.change(screen.getByLabelText('Choose a CSV file'), { target: { files: [file] } });
  };

  it('when a file has mistakes, should list them and not allow saving', async () => {
    vi.mocked(api.importHouseholds).mockResolvedValue({
      new: 1, update: 0, unchanged: 0, error: 1, applied: false,
      rows: [
        { line: 2, meter_id: 'KGL-1', name: 'A B', action: 'new', errors: [], changes: [] },
        { line: 3, meter_id: 'KGL-1', name: 'C D', action: 'error', errors: ['dup_meter:2'], changes: [] },
      ],
    });
    render(<I18nProvider locale="en"><HouseholdImport onImported={vi.fn()} onCancel={vi.fn()} /></I18nProvider>);
    upload('name,phone,meter,sector\n');
    expect(await screen.findByText('The same meter is on line 2.')).toBeInTheDocument();
    expect(api.importHouseholds).toHaveBeenCalledWith('name,phone,meter,sector\n', false);
    expect(screen.getByRole('button', { name: 'Confirm and save 1' })).toBeDisabled();
  });

  it('when the preview is clean, should save on confirm', async () => {
    const onImported = vi.fn();
    vi.mocked(api.importHouseholds)
      .mockResolvedValueOnce({ new: 1, update: 1, unchanged: 0, error: 0, applied: false, rows: [] })
      .mockResolvedValueOnce({ new: 1, update: 1, unchanged: 0, error: 0, applied: true, rows: [] });
    render(<I18nProvider locale="en"><HouseholdImport onImported={onImported} onCancel={vi.fn()} /></I18nProvider>);
    upload('csv');
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm and save 2' }));
    expect(await screen.findByText(/1 added, 1 updated/)).toBeInTheDocument();
    expect(onImported).toHaveBeenCalled();
  });
});
