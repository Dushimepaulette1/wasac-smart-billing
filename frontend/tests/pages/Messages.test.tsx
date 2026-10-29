import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Messages, { SHOWN_TYPES } from '../../src/pages/Messages/Messages';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { TestHousehold } from '../support/household';
import en from '../../src/i18n/locales/en.json';
import { api } from '../../src/api/client';
import type { AnomalyFlag, AnomalyType } from '../../src/api/types';
import { makeFlag } from '../support/fixtures';

vi.mock('../../src/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/api/client')>();
  return { ...actual, api: { ...actual.api, getHouseholdFlags: vi.fn(), deleteMessage: vi.fn() } };
});

const flag = (id: number, anomaly_type: AnomalyType, extra: Partial<AnomalyFlag> = {}) =>
  makeFlag({ id, anomaly_type, ...extra });

const messages: Record<string, string> = en;

/** The message article around a heading. */
function articleFor(heading: HTMLElement): HTMLElement {
  const article = heading.closest('article');
  if (!article) throw new Error('Heading is not inside a message');
  return article;
}

const renderMessages = () =>
  render(
    <I18nProvider locale="en">
<TestHousehold>
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Messages />
      </MemoryRouter>
    </TestHousehold>
</I18nProvider>,
  );

describe('Messages', () => {
  it('when listing message types, should have a title and an explanation for each', () => {
    for (const type of SHOWN_TYPES) {
      expect(messages[`msg.${type}.title`]).toBeTruthy();
      // A location check says which reason; the others have one explanation.
      const noticed = type === 'LOCATION_CHECK' ? ['far', 'no_location', 'imprecise', 'upload'].map((r) => `msg.${type}.${r}`) : [`msg.${type}.noticed`];
      for (const key of noticed) expect(messages[key]).toBeTruthy();
    }
  });

  it('when a first reading was recorded as the starting point, should say the first bill comes next time', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(8, 'NO_BASELINE', { status: 'resolved', requires_staff_review: true, reading_status: 'valid' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'Your first reading' }));
    expect(message).toHaveTextContent('recorded as your starting point');
    expect(within(message).queryByRole('link', { name: 'See your bills' })).not.toBeInTheDocument();
  });

  it('when where a photo was taken is being checked, should tell the household why', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(5, 'LOCATION_CHECK', { features: { location_check: 'upload' }, reading_status: 'pending_review' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: "We're checking where the photo was taken" }));
    expect(message).toHaveTextContent('was chosen from your gallery');
  });

  it('when use is unusually high, should say what was noticed, what to check and what happens next', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(3, 'SPIKE')]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'Much more water than usual' }));
    expect(message).toHaveTextContent('On 09/10/2026, your meter showed much more water');
    expect(within(message).getAllByRole('listitem')).toHaveLength(3);
    expect(message).toHaveTextContent("A WASAC officer is checking this reading. You don't need to do anything.");
    expect(message).not.toHaveTextContent(/text you|SMS|hours/i);
    expect(screen.queryByText(/backend English text/)).not.toBeInTheDocument();
  });

  it('when a checked reading is confirmed, should say so and link to the bill', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(2, 'MISREAD_SUSPECTED', { status: 'resolved', reading_status: 'valid' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'A reading lower than the last one' }));
    expect(message).toHaveTextContent('Checked and confirmed. Your bill is ready.');
    expect(within(message).getByRole('link', { name: 'See your bills' })).toHaveAttribute('href', '/history');
    expect(message).not.toHaveTextContent(/checking/i);
  });

  it('when a checked reading is rejected, should ask to read the meter again', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(2, 'SPIKE', { status: 'resolved', reading_status: 'rejected' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'Much more water than usual' }));
    expect(message).toHaveTextContent('We could not confirm this reading. Please read your meter again.');
    expect(within(message).getByRole('button', { name: 'Read your meter' })).toBeInTheDocument();
  });

  it('when the outcome is not known, should describe the finished check neutrally', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(2, 'MISREAD_SUSPECTED', { status: 'resolved' })]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'A reading lower than the last one' }));
    expect(message).toHaveTextContent('Checked by a WASAC officer.');
    expect(message).not.toHaveTextContent(/checking/i);
  });

  it('when Messages is opened, should mark the messages as seen', async () => {
    window.localStorage.removeItem('wasac.messagesSeenAt:MTR001');
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(3, 'SPIKE')]);
    renderMessages();
    await screen.findByRole('heading', { name: 'Much more water than usual' });
    // Seen per meter, once the list has loaded (an effect, so it may land just after the heading).
    await waitFor(() => expect(Number(window.localStorage.getItem('wasac.messagesSeenAt:MTR001'))).toBeGreaterThan(0));
  });

  it('when a flag needs nothing from the household, should leave it out', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(9, 'NORMAL'), flag(10, 'BASELINE')]);
    renderMessages();
    expect(await screen.findByText(/No messages\./)).toBeInTheDocument();
  });

  it('when a finished message is deleted, should remove it; a reading still being checked has no Delete', async () => {
    vi.mocked(api.deleteMessage).mockResolvedValue(undefined);
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(1, 'SPIKE', { status: 'resolved', reading_status: 'valid', resolved_at: '2026-10-20T10:00:00' }),
      flag(2, 'MISREAD_SUSPECTED', { status: 'open', reading_status: 'pending_review' }),
    ]);
    renderMessages();
    const buttons = await screen.findAllByRole('button', { name: 'Delete' });
    expect(buttons).toHaveLength(1);
    await act(async () => fireEvent.click(buttons[0] as HTMLElement));
    expect(api.deleteMessage).toHaveBeenCalledWith(1);
    expect(screen.queryByRole('heading', { name: 'Much more water than usual' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('article')).toHaveLength(1);
  });
});
