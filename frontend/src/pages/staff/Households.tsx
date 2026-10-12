/**
 * @file Households.tsx
 * @description Every household, searchable by name, meter or sector.
 */

import { useId, useState } from 'react';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import loadOverview from '../../staff/loadOverview';
import HouseholdTable from './HouseholdTable';
import styles from '../../staff/staff.module.css';

function Households() {
  const { t } = useI18n();
  const data = useRequest(loadOverview, { immediate: true, args: [] });
  const [query, setQuery] = useState('');
  const searchId = useId();

  if (data.status !== 'success') {
    return (
      <StaffLayout title={t('staff.nav.households')}>
        <RequestState status={data.status} error={data.error} onRetry={data.retry} />
      </StaffLayout>
    );
  }

  const q = query.trim().toLowerCase();
  const shown = data.data.households.filter(
    (h) => !q || [h.name, h.meter_id, h.sector, h.customer_id].some((v) => v.toLowerCase().includes(q)),
  );

  return (
    <StaffLayout
      title={t('staff.nav.households')}
      lede={t('staff.households.lede', { count: data.data.households.length })}
      reviewCount={data.data.queue.length}
    >
      <section className="panel" aria-label={t('staff.nav.households')}>
        <div>
          <label htmlFor={searchId} className="visually-hidden">
            {t('staff.households.search')}
          </label>
          <input
            id={searchId}
            type="search"
            className={styles.search}
            placeholder={t('staff.households.search')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <p className="visually-hidden" aria-live="polite">
          {t('staff.households.shown', { count: shown.length })}
        </p>
        <HouseholdTable households={shown} />
      </section>
    </StaffLayout>
  );
}

export default Households;
