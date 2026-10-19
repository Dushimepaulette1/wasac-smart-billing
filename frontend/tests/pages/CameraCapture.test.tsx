import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CameraCapture from '../../src/pages/CameraCapture/CameraCapture';
import ConfirmReading from '../../src/pages/ConfirmReading/ConfirmReading';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { SubmissionProvider } from '../../src/household/submission';
import { SAVE_DATA_KEY } from '../../src/household/saveData';
import { jsonResponse, makeGuideFrame, makeNoMeterResponse, makePhotoResponse } from '../support/fixtures';
import type { GuidanceCode, PhotoSubmitResponse } from '../../src/api/types';

// jsdom has no camera or canvas: the frame helpers return fixed images.
vi.mock('../../src/household/photo', () => ({
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
<TestHousehold>
      <SubmissionProvider>
        <MemoryRouter initialEntries={['/submit/camera']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/submit/camera" element={<CameraCapture />} />
            <Route path="/submit/confirm" element={<ConfirmReading />} />
            <Route path="/home" element={<p>Home page</p>} />
          </Routes>
        </MemoryRouter>
      </SubmissionProvider>
    </TestHousehold>
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
  it('when the camera opens, should start with a neutral tip, then show one steady tip at a time', async () => {
    mockBackend([['TOO_FAR', 'GLARE'], ['TOO_FAR']]);
    renderCamera();
    await waitFor(() => expect(tip()).toHaveTextContent("Point the camera at the meter's numbers"), LONG);
    await waitFor(() => expect(tip()).toHaveTextContent('Try moving a little closer to the meter.'), LONG);
    expect(tip()).toHaveAttribute('role', 'status');
    expect(tip()).not.toHaveTextContent('reflection');
  });

  it('when two frames are good, should say "Hold still" and take the photo by itself', async () => {
    const stats = mockBackend([['OK'], ['OK']]);
    renderCamera();
    await waitFor(() => expect(tip()).toHaveTextContent('Hold still…'), LONG);
    await waitFor(() => expect(stats.photo).toBe(1), LONG);
    expect(await screen.findByText('Do these numbers match your meter?')).toBeInTheDocument();
    expect(stats.guide).toBe(2);
  });

  it('when a single answer differs, should keep the tip (no flicker)', async () => {
    mockBackend([['NO_METER'], ['TOO_FAR']]);
    renderCamera();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1200));
    });
    expect(tip()).toHaveTextContent("Point the camera at the meter's numbers");
  });

  it('when the window is framed twice with a lighting hint, should still take the photo by itself', async () => {
    const stats = mockBackend([['GLARE'], ['TOO_DARK']]);
    renderCamera();
    await waitFor(() => expect(stats.photo).toBe(1), LONG);
  });

  it('when checking frames, should never have more than one check in flight', async () => {
    const stats = mockBackend([['TOO_FAR'], ['GLARE'], ['CUT_OFF'], ['TOO_DARK']]);
    renderCamera();
    await waitFor(() => expect(stats.guide).toBe(4), LONG);
    expect(stats.maxInFlight).toBe(1);
  });

  it('when "Save mobile data" is on, should send no live checks, and check the photo after it is taken', async () => {
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

  it('when "Save mobile data" is changed, should remember it on the device', async () => {
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

  it('when no meter is found, should offer "Retake" or "Type the numbers instead"', async () => {
    mockBackend([], makeNoMeterResponse());
    renderCamera();
    await takePhoto();
    expect(await screen.findByText(/We couldn't find a water meter/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retake' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Type the numbers instead' }));
    expect(await screen.findByText('Type your meter reading')).toBeInTheDocument();
  });

  it('when no meter is found and "Retake" is tapped, should open the camera again', async () => {
    mockBackend([], makeNoMeterResponse());
    renderCamera();
    await takePhoto();
    fireEvent.click(await screen.findByRole('button', { name: 'Retake' }));
    expect(await screen.findByRole('button', { name: 'Take photo' })).toBeInTheDocument();
  });

  it('when a problem is fixable, should show the hint and allow using the photo anyway', async () => {
    mockBackend([], makePhotoResponse({ guidance: ['GLARE', 'CHECK_NUMBERS'] }));
    renderCamera();
    await takePhoto();
    expect(await screen.findByText('There may be a reflection. Try tilting the phone slightly.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retake' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Use this photo anyway' }));
    expect(await screen.findByText('Please check the numbers.')).toBeInTheDocument();
    expect(screen.getByAltText('The meter numbers, cut from your photo')).toBeInTheDocument();
  });

  it('when the photo is OK, should go straight to the confirm screen with the number window shown', async () => {
    mockBackend([], makePhotoResponse());
    renderCamera();
    await takePhoto();
    expect(await screen.findByAltText('The meter numbers, cut from your photo')).toBeInTheDocument();
    expect(screen.queryByText('Please check the numbers.')).not.toBeInTheDocument();
  });
});

describe('CameraCapture without a camera', () => {
  it('when camera permission is denied, should offer uploading a photo or typing the numbers', async () => {
    denyCamera();
    renderCamera();
    expect(await screen.findByText('The camera is not available')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Upload a photo' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Type the numbers instead' }));
    expect(await screen.findByText('Type your meter reading')).toBeInTheDocument();
  });
});
