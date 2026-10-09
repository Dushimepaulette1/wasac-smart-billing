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
    expect(message).toHaveTextContent("We're checking this reading. You don't need to do anything.");
    expect(screen.queryByText(/backend English text/)).not.toBeInTheDocument();
  });

  it('describes a finished check without guessing the outcome or still saying "checking"', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(2, 'MISREAD_SUSPECTED', { status: 'resolved' })]);
    renderMessages();
    const message = articleFor(await screen.findByRole('heading', { name: 'A reading lower than the last one' }));
    expect(message).toHaveTextContent("Checked. If we need a new photo, we'll text you.");
    expect(message).not.toHaveTextContent(/checking/i);
  });

  it('leaves out flags a household has nothing to do with', async () => {
    vi.mocked(api.getHouseholdFlags).mockResolvedValue([flag(9, 'NORMAL'), flag(10, 'BASELINE')]);
    renderMessages();
    expect(await screen.findByText(/No messages\./)).toBeInTheDocument();
  });
});
