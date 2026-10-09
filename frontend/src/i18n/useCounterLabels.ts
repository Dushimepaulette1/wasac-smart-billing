/**
 * @file useCounterLabels.ts
 * @description Translated labels for the MeterCounter.
 */

import { useI18n } from './I18nProvider';
import type { MeterCounterLabels } from '../components/MeterCounter/MeterCounter';

export default function useCounterLabels(): MeterCounterLabels {
  const { t } = useI18n();
  return {
    reading: t('counter.reading'),
    cubicMetres: t('counter.cubicMetres'),
    litres: t('counter.litres'),
    cubicMetresLong: t('counter.cubicMetresLong'),
  };
}
