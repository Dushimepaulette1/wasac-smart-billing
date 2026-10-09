/**
 * @file ReadingHeld.jsx
 * @description Submit flow, step 3 when the reading is held for staff to
 * check. Calm and plain: nothing is wrong with the household, they have
 * nothing to do, and they are told what happens next and when.
 */

import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import Screen from '../../components/Screen/Screen';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { isComplete } from '../../utils/reading';
import styles from './ReadingHeld.module.css';

function ReadingHeld() {
  const { t, locale, date } = useI18n();
  const navigate = useNavigate();
  const labels = useCounterLabels();
  // Present when arriving from the confirm screen; after a reload the
  // message still stands on its own.
  const held = useLocation().state;
  const cells = held?.cells && isComplete(held.cells) ? held.cells : null;

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

      {cells && (
        <section className={styles.reading}>
          <h2 className="text-body">{t('held.yourReading')}</h2>
          <MeterCounter cells={cells} labels={labels} locale={locale} />
          {held.at && <p className="text-small text-secondary">{t('held.sentOn', { date: date(held.at) })}</p>}
        </section>
      )}
    </Screen>
  );
}

export default ReadingHeld;
