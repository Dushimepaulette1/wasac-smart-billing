/**
 * @file Sectors.tsx
 * @description Households grouped by sector, the sectors needing attention
 * first: readings held for an officer and possible leaks, then money owed.
 * A table of sectors rather than a map: few meters have a location on file.
 */

import { Link } from 'react-router-dom';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import type { SectorSummary } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import styles from './Sectors.module.css';
import staff from '../../staff/staff.module.css';

/** Readings to check or possible leaks: what puts a sector first. */
function needsAttention(sector: SectorSummary): boolean {
  return sector.held_readings + sector.possible_leaks > 0;
}

function SectorCard({ sector }: { sector: SectorSummary }) {
  const { t, rwf, volume } = useI18n();
  const name = sector.sector || t('staff.sectors.none');
  const urgent = needsAttention(sector);
  return (
    <li className={`panel ${urgent ? 'panel-ink' : ''} ${styles.card}`} aria-label={name}>
      <h2 className="panel-title">{name}</h2>
      <dl className={styles.facts}>
        <div>
          <dt>{t('staff.sectors.households')}</dt>
          <dd className="num">{sector.households}</dd>
        </div>
        <div>
          <dt>{t('staff.sectors.held')}</dt>
          <dd className={`num ${sector.held_readings ? staff.flagged : ''}`}>{sector.held_readings}</dd>
        </div>
        <div>
          <dt>{t('staff.sectors.leaks')}</dt>
          <dd className={`num ${sector.possible_leaks ? staff.flagged : ''}`}>{sector.possible_leaks}</dd>
        </div>
        <div>
          <dt>{t('staff.sectors.usual')}</dt>
          <dd className="num">
            {sector.usual_monthly_m3 == null ? t('staff.sectors.noUsual') : volume(sector.usual_monthly_m3)}
          </dd>
        </div>
        <div>
          <dt>{t('staff.sectors.owed')}</dt>
          <dd className="num">{rwf(sector.owed)}</dd>
        </div>
      </dl>
      {sector.attention.length > 0 && (
        <details className={styles.details}>
          <summary>{t('staff.sectors.show', { count: sector.attention.length })}</summary>
          <ul className={styles.households}>
            {sector.attention.map((h) => (
              <li key={h.customer_id} className={styles.household}>
                <Link to={h.held
                  ? `/staff/review?meter=${encodeURIComponent(h.meter_id)}`
                  : `/staff/households?q=${encodeURIComponent(h.meter_id)}`}>{h.name}</Link>
                <span className="code text-small">{h.meter_id}</span>
                <span className={styles.tags}>
                  {h.held && <span className={staff.flagged}>{t('staff.sectors.heldTag')}</span>}
                  {h.possible_leak && <span className={staff.flagged}>{t('staff.sectors.leakTag')}</span>}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}

function Sectors() {
  const { t } = useI18n();
  const rows = useRequest(api.listSectors, { immediate: true, args: [] });

  return (
    <StaffLayout title={t('staff.nav.sectors')} lede={t('staff.sectors.lede')}>
      {rows.status === 'success' ? (
        rows.data.length === 0 ? (
          <p className={staff.empty}>{t('staff.sectors.empty')}</p>
        ) : (
          <>
            <ul className={styles.list}>
              {rows.data.map((s) => (
                <SectorCard key={s.sector} sector={s} />
              ))}
            </ul>
            <p className="text-small text-secondary">{t('staff.sectors.note')}</p>
          </>
        )
      ) : (
        <RequestState status={rows.status} error={rows.error} onRetry={rows.retry} />
      )}
    </StaffLayout>
  );
}

export default Sectors;
