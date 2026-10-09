import { api, ApiError, cellsToCubicMetreString } from './client';
import { normalizeReading } from '../utils/reading';

const jsonResponse = (status, body) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

// jsdom has no fetch; give spyOn something to replace.
beforeAll(() => {
  if (!global.fetch) global.fetch = () => Promise.reject(new Error('fetch not mocked'));
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe('cellsToCubicMetreString', () => {
  it('puts the decimal point before the 3 litre digits', () => {
    expect(cellsToCubicMetreString(normalizeReading('02813450').cells)).toBe('02813.450');
  });

  it('keeps a padded short reading in cubic metres', () => {
    // The backend reads this with float(): 565.846 m3, not 565846 m3.
    expect(Number(cellsToCubicMetreString(normalizeReading('565846').cells))).toBe(565.846);
  });
});

describe('api', () => {
  it('sends the confirmed reading in cubic metres', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockReturnValue(jsonResponse(200, { success: true }));
    await api.confirmReading({
      customerId: 'CUST001',
      meterId: 'MTR001',
      cells: normalizeReading('00464500').cells,
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/confirm-reading');
    expect(JSON.parse(init.body)).toEqual({
      customer_id: 'CUST001',
      meter_id: 'MTR001',
      confirmed_reading: '00464.500',
    });
  });

  it('reports a dropped connection as offline', async () => {
    jest.spyOn(global, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'offline' });
  });

  it('maps a 404 to notFound and keeps the backend detail', async () => {
    jest.spyOn(global, 'fetch').mockReturnValue(jsonResponse(404, { detail: 'Meter not found' }));
    const error = await api.payBill(99).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe('notFound');
    expect(error.detail).toBe('Meter not found');
  });

  it('maps other failures to server', async () => {
    jest.spyOn(global, 'fetch').mockReturnValue(jsonResponse(500, {}));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'server', status: 500 });
  });

  it('finds the household among all customers', async () => {
    jest.spyOn(global, 'fetch').mockReturnValue(
      jsonResponse(200, [{ customer_id: 'CUST002' }, { customer_id: 'CUST001', name: 'Uwimana' }]),
    );
    await expect(api.getCustomer('CUST001')).resolves.toMatchObject({ name: 'Uwimana' });
  });

  it('asks for flags by meter id', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockReturnValue(jsonResponse(200, []));
    await api.getHouseholdFlags('MTR001');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/anomaly/flags?household_id=MTR001');
  });
});
