import { api, ApiError, cellsToCubicMetreString, setStaffToken } from '../../src/api/client';
import { normalizeReading } from '../../src/utils/reading';
import { jsonResponse as response } from '../support/fixtures';

const jsonResponse = (status: number, body: unknown) => Promise.resolve(response(status, body));

afterEach(() => {
  vi.restoreAllMocks();
});

describe('cellsToCubicMetreString', () => {
  it('when converting cells to cubic metres, should put the decimal point before the 3 litre digits', () => {
    expect(cellsToCubicMetreString(normalizeReading('02813450').cells)).toBe('02813.450');
  });

  it('when the reading was padded, should keep it in cubic metres', () => {
    // The backend reads this with float(): 565.846 m3, not 565846 m3.
    expect(Number(cellsToCubicMetreString(normalizeReading('565846').cells))).toBe(565.846);
  });
});

describe('api', () => {
  it('when confirming a reading, should send it in cubic metres', async () => {
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
      photo_source: 'camera',
      location: null,
    });
  });

  it('when confirming with photo evidence, should send where and how the photo was taken', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, { success: true }));
    await api.confirmReading({
      customerId: 'CUST001',
      meterId: 'MTR001',
      cells: normalizeReading('00464500').cells,
      evidence: { photoSource: 'upload', location: { lat: -1.94, lng: 30.06, accuracyM: 12 } },
    });
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body.photo_source).toBe('upload');
    expect(body.location).toEqual({ lat: -1.94, lng: 30.06, accuracy_m: 12 });
  });

  it('when the connection drops, should report offline', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'offline' });
  });

  it('when the server answers 404, should report notFound and keep the detail', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(404, { detail: 'Meter not found' }));
    const error: unknown = await api.payBill(99).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ kind: 'notFound', detail: 'Meter not found' });
  });

  it('when the server fails in another way, should report a server error', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(500, {}));
    await expect(api.getBills('CUST001')).rejects.toMatchObject({ kind: 'server', status: 500 });
  });

  it('when loading a household, should ask for it by id, not the whole list', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, { customer_id: 'CUST001' }));
    await api.getCustomer('CUST001');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/customers/CUST001');
  });

  it('when a staff member is signed in, should send their token and report when it expires', async () => {
    const onExpired = vi.fn();
    setStaffToken('abc.def', onExpired);
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(401, { detail: 'Sign in to continue.' }));
    await expect(api.reviewQueue()).rejects.toMatchObject({ kind: 'unauthorized' });
    const init = fetchMock.mock.calls[0]?.[1];
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer abc.def');
    expect(onExpired).toHaveBeenCalled();
    setStaffToken(null);
  });

  it('when nobody is signed in, should send no token for household requests', async () => {
    setStaffToken(null);
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, []));
    await api.getBills('CUST001');
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('when loading messages, should ask for flags by meter id', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(200, []));
    await api.getHouseholdFlags('MTR001');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/anomaly/flags?household_id=MTR001');
  });
});

describe('rate limits and size limits', () => {
  it('when a photo endpoint answers 429, should report "too many", not a sign-in lockout', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(429, { detail: 'Too many photos' }));
    await expect(api.submitPhoto(new Blob(['p']))).rejects.toMatchObject({ kind: 'tooMany', status: 429 });
  });

  it('when sign-in answers 429, should report the lockout', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(429, { detail: 'Too many wrong attempts' }));
    await expect(api.login('officer1', 'x')).rejects.toMatchObject({ kind: 'locked' });
  });

  it('when the server answers 413, should report the photo as too large', async () => {
    vi.spyOn(globalThis, 'fetch').mockReturnValue(jsonResponse(413, { detail: 'Image larger than 10 MB' }));
    await expect(api.submitPhoto(new Blob(['p']))).rejects.toMatchObject({ kind: 'tooLarge' });
  });
});
