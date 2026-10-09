/**
 * @file useCounterLabels.js
 * @description Translated labels for the MeterCounter.
 */

import { useI18n } from './I18nProvider';

export default function useCounterLabels() {
  const { t } = useI18n();
  return {
    reading: t('counter.reading'),
    cubicMetres: t('counter.cubicMetres'),
    litres: t('counter.litres'),
    cubicMetresLong: t('counter.cubicMetresLong'),
  };
}
