import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ConfirmReading from '../../src/pages/ConfirmReading/ConfirmReading';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import { SubmissionProvider, type Submission } from '../../src/household/submission';
import { jsonResponse, makeAnomalyResult, makeConfirmResponse } from '../support/fixtures';
import { normalizeReading } from '../../src/utils/reading';

function renderWith(fromReader: string, extra: Partial<Submission> = {}) {
  const { cells, needsCheck, raw } = normalizeReading(fromReader);
  const initial: Submission = {
    photo: null,
    raw,
    confidence: 0.9,
    cells,
    needsCheck,
    manual: false,
    crop: null,
    checkNumbers: false,
    evidence: null,
    ...extra,
  };
  return render(
    <I18nProvider locale="en">
<TestHousehold>
      <SubmissionProvider initial={initial}>
        <MemoryRouter
          initialEntries={['/submit/confirm']}
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <Routes>
            <Route path="/submit/confirm" element={<ConfirmReading />} />
            <Route path="/bill" element={<p>Bill page</p>} />
            <Route path="/submit/held" element={<p>Held page</p>} />
          </Routes>
        </MemoryRouter>
      </SubmissionProvider>
    </TestHousehold>
</I18nProvider>,
  );
}

const fine = { needs_review: false, reason: null, previous_reading_m3: 464, consumption_m3: 20, refused: null, opens_on: null };

/** The two calls behind "Confirm reading": the check, then the sending. */
function server(check: unknown, confirm: unknown = makeConfirmResponse()) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((url) =>
    String(url).includes('/check-reading')
      ? check instanceof Error ? Promise.reject(check) : Promise.resolve(jsonResponse(200, check))
      : Promise.resolve(jsonResponse(200, confirm)),
  );
}

const sentTo = (spy: ReturnType<typeof server>) => spy.mock.calls.map(([url]) => String(url).split('/').pop());

const clickConfirm = async () => {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
  });
};

const counterCells = (container: HTMLElement) =>
  [...container.querySelectorAll('[class*="cell"]')].map((c) => c.textContent).join('|');

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

const held = makeConfirmResponse({
  bill_id: null,
  bill_amount: null,
  validation_status: 'pending_review',
  anomaly_flagged: true,
  anomaly: makeAnomalyResult({ pending_review: true }),
});

const lower = { ...fine, needs_review: true, reason: 'below_previous', consumption_m3: -0.06, previous_reading_m3: 431.46 };

describe('ConfirmReading', () => {
  it('when the reading has the wrong length, should show it above an empty counter', () => {
    const { container } = renderWith('005162454');
    const message = screen.getByText(
      (_, el) =>
        el?.tagName === 'P' &&
      el.textContent === 'We read 005162454. Check the numbers on your meter and type them here.',
    );
    expect(message).toBeInTheDocument();
    expect(screen.getByText('005162454').tagName).toBe('STRONG');
    // The counter is empty and ready for typing, not an error.
    expect(counterCells(container)).toBe('|||||||');
    expect(screen.getByLabelText('Meter reading')).toHaveFocus();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('when the reading is short, should pad it onto the counter without asking to retype it', () => {
    const { container } = renderWith('565846');
    expect(counterCells(container)).toBe('0|0|5|6|5|8|4|6');
    expect(screen.getByText('Do these numbers match your meter?')).toBeInTheDocument();
  });

  it('when the reader was unsure, should say "Please check the numbers." and still allow confirming', () => {
    renderWith('02813450', { checkNumbers: true });
    expect(screen.getByText('Please check the numbers.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm reading' })).toBeEnabled();
  });

  it('when the reader was confident, should not ask to check the numbers', () => {
    renderWith('02813450', { confidence: 0.55 });
    expect(screen.queryByText('Please check the numbers.')).not.toBeInTheDocument();
  });

  it('when a crop is available, should show the number window above the counter', () => {
    const { container } = renderWith('02813450', { photo: 'data:image/jpeg;base64,BBBB', crop: 'data:image/jpeg;base64,AAAA' });
    const crop = screen.getByAltText('The meter numbers, cut from your photo');
    const counter = screen.getByLabelText('Meter reading');
    // The crop comes first in the reading panel; the full photo is not repeated beside it.
    expect(crop.compareDocumentPosition(counter) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelectorAll('img')).toHaveLength(1);
  });

  it('when numbers are missing, should ask for all 8 instead of sending', () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    renderWith('005162454');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Fill in all 8 numbers');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('when the reading creates a bill, should go to the bill', async () => {
    const spy = server(fine, makeConfirmResponse({ bill_id: 7 }));
    renderWith('00484500');
    await clickConfirm();
    expect(await screen.findByText('Bill page')).toBeInTheDocument();
    expect(sentTo(spy)).toEqual(['check-reading', 'confirm-reading']); // one tap, no extra step
  });

  it('when the reading is held, should go to the held screen', async () => {
    // The check said fine, but the situation changed before sending: the backend's answer decides.
    server(fine, held);
    renderWith('00000444');
    await clickConfirm();
    expect(await screen.findByText('Held page')).toBeInTheDocument();
  });

  it('when sending fails, should keep the typed numbers', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) =>
      String(url).includes('/check-reading')
        ? Promise.resolve(jsonResponse(200, fine))
        : Promise.reject(new TypeError('Failed to fetch')),
    );
    const { container } = renderWith('00484500');
    await clickConfirm();
    expect(screen.getByRole('alert')).toHaveTextContent('No connection');
    expect(screen.getByRole('alert')).toHaveTextContent('Your numbers are saved.');
    expect(counterCells(container)).toBe('0|0|4|8|4|5|0|0');
  });

  it('when the reading needs review, should explain why and send nothing yet', async () => {
    const spy = server(lower);
    renderWith('00431400');
    await clickConfirm();
    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent('lower than your previous accepted reading, 431.460 m³');
    expect(notice).toHaveTextContent('you can send it for review');
    expect(screen.getByRole('button', { name: 'Check the digits' })).toBeInTheDocument();
    expect(sentTo(spy)).toEqual(['check-reading']);
  });

  it('when the household chooses to check the digits, should go back with the numbers kept', async () => {
    const spy = server(lower);
    const { container } = renderWith('00431400');
    await clickConfirm();
    fireEvent.click(screen.getByRole('button', { name: 'Check the digits' }));
    expect(screen.queryByRole('button', { name: 'Send for review' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm reading' })).toBeInTheDocument();
    expect(counterCells(container)).toBe('0|0|4|3|1|4|0|0');
    expect(sentTo(spy)).toEqual(['check-reading']);
  });

  it('when the household sends it for review, should submit it and go to the held screen', async () => {
    const spy = server(lower, held);
    renderWith('00431400');
    await clickConfirm();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Send for review' }));
    });
    expect(await screen.findByText('Held page')).toBeInTheDocument();
    expect(sentTo(spy)).toEqual(['check-reading', 'confirm-reading']);
  });

  it.each([
    ['first_reading', 'first reading for your meter'],
    ['high_use', 'much more water'],
    ['misread', 'digit is in the wrong place'],
    ['edited_down', 'numbers we read in your photo'],
    ['location', 'could not confirm this photo'],
  ])('when the reason is %s, should say so in plain words', async (reason, words) => {
    server({ ...fine, needs_review: true, reason });
    renderWith('00484500');
    await clickConfirm();
    expect(screen.getByRole('status')).toHaveTextContent(words);
  });

  it('when the check fails, should send nothing, keep the numbers and offer to try again', async () => {
    const spy = server(new TypeError('Failed to fetch'));
    const { container } = renderWith('00484500');
    await clickConfirm();
    expect(screen.getByRole('alert')).toHaveTextContent('it was not sent');
    expect(sentTo(spy)).toEqual(['check-reading']);
    expect(counterCells(container)).toBe('0|0|4|8|4|5|0|0');
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('when the reading cannot be sent now, should say so and send nothing', async () => {
    const spy = server({ ...fine, refused: 'pending' });
    renderWith('00484500');
    await clickConfirm();
    expect(screen.getByRole('status')).toHaveTextContent("can't be sent now");
    expect(sentTo(spy)).toEqual(['check-reading']);
  });
});
