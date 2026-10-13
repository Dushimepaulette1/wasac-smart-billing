import { api, ApiError, cellsToCubicMetreString, setStaffToken } from './client';
import { normalizeReading } from '../utils/reading';
import { jsonResponse as response } from '../test/fixtures';

const jsonResponse = (status: number, body: unknown) => Promise.resolve(response(status, body));

afterEach(() => {
  vi.restoreAllMocks();
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
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, { success: true }));
    await api.confirmReading({
      customerId: 'CUST001',
      meterId: 'MTR001',
      cells: normalizeReading('00464500').cells,
    });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe('/confirm-reading');
    expect(JSON.parse(String(init?.body))).toEqual({
      customer_id: 'CUST001',
      meter_id: 'MTR001',
      confirmed_reading: '00464.500',
    });
  });

  it('reports a dropped connection as offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'offline' });
  });

  it('maps a 404 to notFound and keeps the backend detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(404, { detail: 'Meter not found' }));
    const error: unknown = await api.payBill(99).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: 'notFound', detail: 'Meter not found' });
  });

  it('maps other failures to server', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(500, {}));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'server', status: 500 });
  });

  it('asks for the household by id, not the whole customer list', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, { customer_id: 'CUST001' }));
    await api.getCustomer('CUST001');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/customers/CUST001');
  });

  it('sends the staff token, and reports an expired one', async () => {
    const onExpired = vi.fn();
    setStaffToken('abc.def', onExpired);
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(401, { detail: 'Sign in to continue.' }));
    await expect(api.reviewQueue()).rejects.toMatchObject({ kind: 'unauthorized' });
    const init = fetchMock.mock.calls[0]?.[1];
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer abc.def');
    expect(onExpired).toHaveBeenCalled();
    setStaffToken(null);
  });

  it('sends no token for household requests when nobody is signed in', async () => {
    setStaffToken(null);
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, []));
    await api.getBills('CUST001');
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('asks for flags by meter id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, []));
    await api.getHouseholdFlags('MTR001');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/anomaly/flags?household_id=MTR001');
  });
});

describe('rate limits and size limits', () => {
  it('reports a 429 on a photo endpoint as "too many", not as a sign-in lockout', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(429, { detail: 'Too many photos' }));
    await expect(api.submitPhoto(new Blob(['p']))).rejects.toMatchObject({ kind: 'tooMany', status: 429 });
  });

  it('keeps a 429 on sign-in as the lockout', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(429, { detail: 'Too many wrong attempts' }));
    await expect(api.login('officer1', 'x')).rejects.toMatchObject({ kind: 'locked' });
  });

  it('reports a 413 as a photo that is too large', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(413, { detail: 'Image larger than 10 MB' }));
    await expect(api.submitPhoto(new Blob(['p']))).rejects.toMatchObject({ kind: 'tooLarge' });
  });
});
