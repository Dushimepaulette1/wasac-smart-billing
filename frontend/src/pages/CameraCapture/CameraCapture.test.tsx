import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CameraCapture from './CameraCapture';
import ConfirmReading from '../ConfirmReading/ConfirmReading';
import { I18nProvider } from '../../i18n/I18nProvider';
import { SubmissionProvider } from '../../household/submission';
import { SAVE_DATA_KEY } from '../../household/saveData';
import { jsonResponse, makeGuideFrame, makeNoMeterResponse, makePhotoResponse } from '../../test/fixtures';
import type { GuidanceCode, PhotoSubmitResponse } from '../../api/types';

// jsdom has no camera or canvas: the frame helpers return fixed images.
vi.mock('../../household/photo', () => ({
  frameToBlob: () => Promise.resolve(new Blob(['frame'], { type: 'image/jpeg' })),
  frameToDataUrl: () => 'data:image/jpeg;base64,UEhPVE8=',
  fileToDataUrl: () => Promise.resolve('data:image/jpeg;base64,UEhPVE8='),
  dataUrlToBlob: () => new Blob(['photo'], { type: 'image/jpeg' }),
}));

const stopTrack = vi.fn();

function grantCamera() {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) },
  });
}

function denyCamera() {
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')) },
  });
}

/**
 * Fake backend: /guide-frame answers with `frames` in order (then never
 * answers again), /submit-photo with `photo`. Tracks requests in flight.
 */
function mockBackend(frames: GuidanceCode[][], photo: PhotoSubmitResponse = makePhotoResponse()) {
  const stats = { guide: 0, photo: 0, inFlight: 0, maxInFlight: 0 };
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith('/guide-frame')) {
      const next = frames.shift();
      if (!next) return new Promise<Response>(() => undefined);
      stats.guide += 1;
      stats.inFlight += 1;
      stats.maxInFlight = Math.max(stats.maxInFlight, stats.inFlight);
      await new Promise((r) => setTimeout(r, 5));
      stats.inFlight -= 1;
      return jsonResponse(200, makeGuideFrame(next));
    }
    if (url.endsWith('/submit-photo')) {
      stats.photo += 1;
      return jsonResponse(200, photo);
    }
    throw new Error(`unexpected request ${url}`);
  });
  return stats;
}

function renderCamera() {
  return render(
    <I18nProvider locale="en">
      <SubmissionProvider>
        <MemoryRouter initialEntries={['/submit/camera']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/submit/camera" element={<CameraCapture />} />
            <Route path="/submit/confirm" element={<ConfirmReading />} />
            <Route path="/home" element={<p>Home page</p>} />
          </Routes>
        </MemoryRouter>
      </SubmissionProvider>
    </I18nProvider>,
  );
}

const tip = () => document.querySelector('[aria-live="polite"]');
const LONG = { timeout: 3000 };

beforeEach(() => grantCamera());

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

describe('CameraCapture live tips', () => {
  it('shows one tip at a time in a polite live region', async () => {
    mockBackend([['TOO_FAR', 'GLARE']]);
    renderCamera();
    await waitFor(() => expect(tip()).toHaveTextContent('Try moving a little closer to the meter.'), LONG);
    expect(tip()).toHaveAttribute('role', 'status');
    expect(tip()).not.toHaveTextContent('reflection');
  });

  it('takes the photo by itself after two good frames, with "Hold still" first', async () => {
    const stats = mockBackend([['OK'], ['OK']]);
    renderCamera();
    await waitFor(() => expect(tip()).toHaveTextContent('Hold still…'), LONG);
    await waitFor(() => expect(stats.photo).toBe(1), LONG);
    expect(await screen.findByText('Do these numbers match your meter?')).toBeInTheDocument();
    expect(stats.guide).toBe(2);
  });

  it('never has more than one live check in flight', async () => {
    const stats = mockBackend([['TOO_FAR'], ['GLARE'], ['CUT_OFF'], ['TOO_DARK']]);
    renderCamera();
    await waitFor(() => expect(stats.guide).toBe(4), LONG);
    expect(stats.maxInFlight).toBe(1);
  });

  it('sends no live checks in "Save mobile data" mode, and checks the photo after it is taken', async () => {
    window.localStorage.setItem(SAVE_DATA_KEY, '1');
    const stats = mockBackend([['OK'], ['OK']]);
    renderCamera();
    expect(await screen.findByText('Live tips are off to save mobile data.')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /Save mobile data/ })).toBeChecked();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 300));
    });
    expect(stats.guide).toBe(0);
    fireEvent.click(screen.getByRole('button', { name: 'Take photo' }));
    await waitFor(() => expect(stats.photo).toBe(1));
  });

  it('remembers the "Save mobile data" choice on the device', async () => {
    mockBackend([]);
    renderCamera();
    fireEvent.click(await screen.findByRole('switch', { name: /Save mobile data/ }));
    expect(window.localStorage.getItem(SAVE_DATA_KEY)).toBe('1');
  });
});

describe('CameraCapture after the photo', () => {
  beforeEach(() => window.localStorage.setItem(SAVE_DATA_KEY, '1'));

  const takePhoto = async () => {
    fireEvent.click(await screen.findByRole('button', { name: 'Take photo' }));
  };

  it('NO_METER: no reading, "Retake" or "Type the numbers instead"', async () => {
    mockBackend([], makeNoMeterResponse());
    renderCamera();
    await takePhoto();
    expect(await screen.findByText(/We couldn't find a water meter/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retake' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Type the numbers instead' }));
    expect(await screen.findByText('Type your meter reading')).toBeInTheDocument();
  });

  it('NO_METER: "Retake" opens the camera again', async () => {
    mockBackend([], makeNoMeterResponse());
    renderCamera();
    await takePhoto();
    fireEvent.click(await screen.findByRole('button', { name: 'Retake' }));
    expect(await screen.findByRole('button', { name: 'Take photo' })).toBeInTheDocument();
  });

  it('soft retake: shows the hint and lets the household use the photo anyway', async () => {
    mockBackend([], makePhotoResponse({ guidance: ['GLARE', 'CHECK_NUMBERS'] }));
    renderCamera();
    await takePhoto();
    expect(await screen.findByText('There may be a reflection. Try tilting the phone slightly.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retake' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Use this photo anyway' }));
    expect(await screen.findByText('Please check the numbers.')).toBeInTheDocument();
    expect(screen.getByAltText('The meter numbers, cut from your photo')).toBeInTheDocument();
  });

  it('OK: goes straight to the confirm screen with the number window above the counter', async () => {
    mockBackend([], makePhotoResponse());
    renderCamera();
    await takePhoto();
    expect(await screen.findByAltText('The meter numbers, cut from your photo')).toBeInTheDocument();
    expect(screen.queryByText('Please check the numbers.')).not.toBeInTheDocument();
  });
});

describe('CameraCapture without a camera', () => {
  it('offers uploading a photo or typing the numbers when permission is denied', async () => {
    denyCamera();
    renderCamera();
    expect(await screen.findByText('The camera is not available')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload a photo' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Type the numbers instead' }));
    expect(await screen.findByText('Type your meter reading')).toBeInTheDocument();
  });
});
