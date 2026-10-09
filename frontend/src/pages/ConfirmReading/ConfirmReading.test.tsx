import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ConfirmReading from './ConfirmReading';
import { I18nProvider } from '../../i18n/I18nProvider';
import { SubmissionProvider, type Submission } from '../../household/submission';
import { jsonResponse, makeAnomalyResult, makeConfirmResponse } from '../../test/fixtures';
import { normalizeReading } from '../../utils/reading';

function renderWith(fromReader: string, extra: Partial<Submission> = {}) {
  const { cells, needsCheck, raw } = normalizeReading(fromReader);
  const initial: Submission = { photo: null, raw, confidence: 0.9, cells, needsCheck, manual: false, ...extra };
  return render(
    <I18nProvider locale="en">
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
    </I18nProvider>,
  );
}

const counterCells = (container: HTMLElement) =>
  [...container.querySelectorAll('[class*="cell"]')].map((c) => c.textContent).join('|');

afterEach(() => {
  vi.restoreAllMocks();
  window.sessionStorage.clear();
});

describe('ConfirmReading', () => {
  it('shows the raw wrong-length reading above an empty editable counter', () => {
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

  it('pads a short reading onto the counter without asking to retype it', () => {
    const { container } = renderWith('565846');
    expect(counterCells(container)).toBe('0|0|5|6|5|8|4|6');
    expect(screen.getByText('Do these numbers match your meter?')).toBeInTheDocument();
  });

  it('keeps Confirm reading enabled while the blurry-photo prompt shows', () => {
    renderWith('02813450', { confidence: 0.5 });
    expect(screen.getByText(/may be blurry/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm reading' })).toBeEnabled();
  });

  it('asks for all 8 numbers instead of sending an incomplete reading', () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    renderWith('005162454');
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Fill in all 8 numbers');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('goes to the bill when the reading creates one', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(jsonResponse(200, makeConfirmResponse({ bill_id: 7 })));
    renderWith('00484500');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
    });
    expect(await screen.findByText('Bill page')).toBeInTheDocument();
  });

  it('goes to the held screen when the reading is held for checking', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      jsonResponse(
        200,
        makeConfirmResponse({
          bill_id: null,
          bill_amount: null,
          validation_status: 'pending_review',
          anomaly_flagged: true,
          anomaly: makeAnomalyResult({ pending_review: true }),
        }),
      ),
    );
    renderWith('00000444');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
    });
    expect(await screen.findByText('Held page')).toBeInTheDocument();
  });

  it('keeps the typed numbers when sending fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));
    const { container } = renderWith('00484500');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm reading' }));
    });
    expect(screen.getByRole('alert')).toHaveTextContent('No connection');
    expect(screen.getByRole('alert')).toHaveTextContent('Your numbers are saved.');
    expect(counterCells(container)).toBe('0|0|4|8|4|5|0|0');
  });
});
