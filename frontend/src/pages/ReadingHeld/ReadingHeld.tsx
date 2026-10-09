/**
 * @file ReadingHeld.tsx
 * @description Submit flow, step 3 when the reading is held for staff to
 * check. Calm and plain: nothing is wrong with the household, they have
 * nothing to do, and they are told what happens next and when.
 */

import { useLocation, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { isComplete, type Cells } from '../../utils/reading';
import styles from './ReadingHeld.module.css';

/** What the confirm screen passes along: the reading sent and its local date. */
export interface HeldState {
  cells: Cells;
  at: string;
}

/** Router state is untyped and may be anything (history, another tab), so check it. */
function readHeldState(state: unknown): HeldState | null {
  if (!state || typeof state !== 'object') return null;
  const { cells, at } = state as Partial<Record<keyof HeldState, unknown>>;
  if (!Array.isArray(cells) || !cells.every((c) => typeof c === 'string')) return null;
  return isComplete(cells) ? { cells, at: typeof at === 'string' ? at : '' } : null;
}

function ReadingHeld() {
  const { t, locale, date } = useI18n();
  const navigate = useNavigate();
  const labels = useCounterLabels();
  // Present when arriving from the confirm screen; after a reload the
  // message still stands on its own.
  const held = readHeldState(useLocation().state);

  return (
    <Screen
      title={t('held.title')}
      step={t('flow.step', { current: 3, total: 3 })}
      action={
        <Button fullWidth onClick={() => navigate('/home')}>
          {t('action.backHome')}
        </Button>
      }
    >
      <Notice tone="held" live title={t('held.checkingTitle')}>
        {t('held.checkingBody')}
      </Notice>

      {held && (
        <section className={styles.reading}>
          <h2 className="text-body">{t('held.yourReading')}</h2>
          <MeterCounter cells={held.cells} labels={labels} locale={locale} />
          {held.at && <p className="text-small text-secondary">{t('held.sentOn', { date: date(held.at) })}</p>}
        </section>
      )}
    </Screen>
  );
}

export default ReadingHeld;
