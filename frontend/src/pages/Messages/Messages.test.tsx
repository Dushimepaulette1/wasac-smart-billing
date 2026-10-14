import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Messages, { SHOWN_TYPES } from './Messages';
import { I18nProvider } from '../../i18n/I18nProvider';
import en from '../../i18n/locales/en.json';
import { api } from '../../api/client';
import type { AnomalyFlag, AnomalyType } from '../../api/types';
import { makeFlag } from '../../test/fixtures';

vi.mock('../../api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/client')>();
  return { ...actual, api: { ...actual.api, getHouseholdFlags: vi.fn() } };
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
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Messages />
      </MemoryRouter>
    </I18nProvider>,
  );

describe('Messages', () => {
  it('has a title and an explanation for every type it shows', () => {
    for (const type of SHOWN_TYPES) {
      expect(messages[`msg.${type}.title`]).toBeTruthy();
      expect(messages[`msg.${type}.noticed`]).toBeTruthy();
    }
  });

  it('tells a household what was noticed, what to check and what happens next', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(3, 'SPIKE')]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'Much more water than usual' }));
    expect(message).toHaveTextContent('On 09/10/2026, your meter showed much more water');
    expect(within(message).getAllByRole('listitem')).toHaveLength(3);
    expect(message).toHaveTextContent("A WASAC officer is checking this reading. You don't need to do anything.");
    expect(message).not.toHaveTextContent(/text you|SMS|hours/i);
    expect(screen.queryByText(/backend English text/)).not.toBeInTheDocument();
  });

  it('says a checked reading was confirmed, with a way to the bill', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(2, 'MISREAD_SUSPECTED', { status: 'resolved', reading_status: 'valid' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'A reading lower than the last one' }));
    expect(message).toHaveTextContent('Checked and confirmed. Your bill is ready.');
    expect(within(message).getByRole('link', { name: 'See your bills' })).toHaveAttribute('href', '/history');
    expect(message).not.toHaveTextContent(/checking/i);
  });

  it('asks to read the meter again when a checked reading was not confirmed', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([
      flag(2, 'SPIKE', { status: 'resolved', reading_status: 'rejected' }),
    ]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'Much more water than usual' }));
    expect(message).toHaveTextContent('We could not confirm this reading. Please read your meter again.');
    expect(within(message).getByRole('button', { name: 'Read your meter' })).toBeInTheDocument();
  });

  it('describes a finished check neutrally when the outcome is not known', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(2, 'MISREAD_SUSPECTED', { status: 'resolved' })]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'A reading lower than the last one' }));
    expect(message).toHaveTextContent('Checked by a WASAC officer.');
    expect(message).not.toHaveTextContent(/checking/i);
  });

  it('marks messages as seen when Messages is opened', async () => {
    window.localStorage.removeItem('wasac.messagesSeenAt');
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(3, 'SPIKE')]);
    renderMessages();
    await screen.findByRole('heading', { name: 'Much more water than usual' });
    expect(Number(window.localStorage.getItem('wasac.messagesSeenAt'))).toBeGreaterThan(0);
  });

  it('leaves out flags a household has nothing to do with', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(9, 'NORMAL'), flag(10, 'BASELINE')]);
    renderMessages();
    expect(await screen.findByText(/No messages\./)).toBeInTheDocument();
  });
});
