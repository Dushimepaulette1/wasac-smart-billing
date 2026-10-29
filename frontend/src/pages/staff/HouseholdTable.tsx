/**
 * @file HouseholdTable.tsx
 * @description Households as a table on wide screens, stacked cards on
 * narrow ones (labels come from data-label).
 */

import Button from '../../components/Button/Button';
import Icon from '../../components/Icon/Icon';
import { useI18n } from '../../i18n/I18nProvider';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import type { HouseholdRow } from '../../staff/loadOverview';
import styles from '../../staff/staff.module.css';

interface HouseholdTableProps {
  households: HouseholdRow[];
  /** Fewer columns, for the overview. */
  compact?: boolean;
  /** Shows an Edit button on each row. */
  onEdit?: (household: HouseholdRow) => void;
}

function HouseholdTable({ households, compact = false, onEdit }: HouseholdTableProps) {
  const { t, rwf, volume, date } = useI18n();
  if (households.length === 0) return <p className={styles.empty}>{t('staff.households.none')}</p>;
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{t('staff.col.household')}</th>
            {!compact && <th scope="col">{t('staff.col.meter')}</th>}
            <th scope="col" className={styles.right}>
              {t('staff.col.lastReading')}
            </th>
            {!compact && (
              <th scope="col" className={styles.right}>
                {t('staff.col.usual')}
              </th>
            )}
            <th scope="col" className={styles.right}>
              {t('staff.col.unpaid')}
            </th>
            <th scope="col">{t('staff.col.status')}</th>
            {onEdit && (
              <th scope="col">
                <span className="visually-hidden">{t('staff.accounts.col.actions')}</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {households.map((h) => (
            <tr key={h.customer_id}>
              <td>
                {h.name}
                {h.is_demo && <span className={styles.you}> {t('staff.households.test')}</span>}
                <span className={styles.cellSub}>{h.sector}</span>
                {compact && <span className={`${styles.cellSub} code`}>{h.meter_id}</span>}
              </td>
              {!compact && (
                <td data-label={t('staff.col.meter')} className="code">
                  {h.meter_id}
                  {h.serial_number && <span className={styles.cellSub}>{t('staff.households.serial', { serial: h.serial_number })}</span>}
                </td>
              )}
              <td data-label={t('staff.col.lastReading')} className={styles.right}>
                <span>
                  {formatReading(cellsFromCubicMetres(h.last_reading))} m³
                  {h.last_reading_date && <span className={styles.cellSub}>{date(h.last_reading_date)}</span>}
                </span>
              </td>
              {!compact && (
                <td data-label={t('staff.col.usual')} className={styles.right}>
                  {h.avg_consumption !== null ? `${volume(h.avg_consumption)}` : '–'}
                </td>
              )}
              <td data-label={t('staff.col.unpaid')} className={styles.right}>
                {h.unpaidCount ? rwf(h.unpaidAmount) : t('staff.col.none')}
              </td>
              <td data-label={t('staff.col.status')}>
                {h.anomaly_flagged ? (
                  <span className={`${styles.status} ${styles.flagged}`}>
                    <Icon name="clock" size={18} />
                    {t('staff.status.checking')}
                  </span>
                ) : (
                  <span className={styles.status}>
                    <Icon name="check" size={18} />
                    {t('staff.status.ok')}
                  </span>
                )}
              </td>
              {onEdit && (
                <td data-label={t('staff.accounts.col.actions')}>
                  <Button variant="text" onClick={() => onEdit(h)} aria-label={t('staff.household.editFor', { name: h.name })}>
                    {t('staff.household.edit')}
                  </Button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default HouseholdTable;
