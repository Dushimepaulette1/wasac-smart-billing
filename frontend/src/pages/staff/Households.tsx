/**
 * @file Households.tsx
 * @description Every household, searchable by name, meter or sector. Staff
 * add a household or edit one (a new phone number, say); supervisors and
 * admins can also upload WASAC's customer list as a CSV and correct a
 * meter's current reading.
 */

import { useEffect, useId, useRef, useState } from 'react';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import loadOverview, { type HouseholdRow } from '../../staff/loadOverview';
import HouseholdTable from './HouseholdTable';
import HouseholdForm from './HouseholdForm';
import HouseholdImport from './HouseholdImport';
import MeterCorrection from './MeterCorrection';
import { hasRole, useAuth } from '../../staff/auth';
import type { CustomerInfo } from '../../api/types';
import styles from '../../staff/staff.module.css';

type Open = { kind: 'add' } | { kind: 'edit'; household: HouseholdRow } | { kind: 'import' } | null;

function Households() {
  const { t } = useI18n();
  const data = useRequest(loadOverview, { immediate: true, args: [] });
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState<Open>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const searchId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) panel.current?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [open]);

  if (data.status !== 'success') {
    return (
      <StaffLayout title={t('staff.nav.households')}>
        <RequestState status={data.status} error={data.error} onRetry={data.retry} />
      </StaffLayout>
    );
  }

  const q = query.trim().toLowerCase();
  const shown = data.data.households.filter(
    (h) => !q || [h.name, h.meter_id, h.sector, h.customer_id, h.phone, h.serial_number ?? '']
      .some((v) => v.toLowerCase().includes(q)),
  );
  const supervisor = hasRole(user, 'supervisor');

  const onSaved = (customer: CustomerInfo, added: boolean) => {
    setOpen(null);
    setSaved(t(added ? 'staff.household.added' : 'staff.household.saved', { name: customer.name, meter: customer.meter_id }));
    data.retry();
  };

  return (
    <StaffLayout
      title={t('staff.nav.households')}
      lede={t('staff.households.lede', { count: data.data.households.length })}
      reviewCount={data.data.queue.length}
    >
      <div className={styles.stack}>
        <div className={styles.rowActions}>
          <Button icon="plus" onClick={() => { setSaved(null); setOpen({ kind: 'add' }); }}>
            {t('staff.household.addButton')}
          </Button>
          {supervisor && (
            <Button variant="secondary" icon="upload" onClick={() => { setSaved(null); setOpen({ kind: 'import' }); }}>
              {t('staff.import.button')}
            </Button>
          )}
        </div>

        {saved && (
          <Notice tone="done" live>
            {saved}
          </Notice>
        )}

        {open && (
          <div ref={panel}>
            {open.kind === 'add' && <HouseholdForm onSaved={(c) => onSaved(c, true)} onCancel={() => setOpen(null)} />}
            {open.kind === 'edit' && (
              <HouseholdForm
                key={open.household.customer_id}
                household={open.household}
                onSaved={(c) => onSaved(c, false)}
                onCancel={() => setOpen(null)}
              />
            )}
            {open.kind === 'import' && <HouseholdImport onImported={data.retry} onCancel={() => setOpen(null)} />}
          </div>
        )}

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
          <HouseholdTable households={shown} onEdit={(h) => { setSaved(null); setOpen({ kind: 'edit', household: h }); }} />
        </section>

        {supervisor && <MeterCorrection households={data.data.households} onCorrected={data.retry} />}
      </div>
    </StaffLayout>
  );
}

export default Households;
