/**
 * @file Corrections.tsx
 * @description Supervisors and admins: setting a meter's starting reading, and correcting a billed
 * reading. Both change what a household is charged, so anything that could raise or hide a charge
 * waits here for a second person.
 */

import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import loadOverview from '../../staff/loadOverview';
import MeterCorrection from './MeterCorrection';
import BillCorrection from './BillCorrection';
import styles from '../../staff/staff.module.css';

function Corrections() {
  const { t } = useI18n();
  const data = useRequest(loadOverview, { immediate: true, args: [] });

  return (
    <StaffLayout title={t('staff.nav.corrections')} lede={t('staff.corrections.lede')}>
      {data.status === 'success' ? (
        <div className={styles.stack}>
          <MeterCorrection households={data.data.households} onCorrected={data.retry} />
          <BillCorrection households={data.data.households} onCorrected={data.retry} />
        </div>
      ) : (
        <RequestState status={data.status} error={data.error} onRetry={data.retry} />
      )}
    </StaffLayout>
  );
}

export default Corrections;
