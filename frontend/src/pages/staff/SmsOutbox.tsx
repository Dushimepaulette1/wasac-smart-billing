/**
 * @file SmsOutbox.tsx
 * @description Admins only: the SMS the server sent through the Africa's
 * Talking sandbox, newest first. The sandbox never delivers to real phones and
 * its simulator is not always available, so this is where a demo's sign-in
 * codes and notices can be read. Live SMS are never stored.
 */

import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import Button from '../../components/Button/Button';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import { dateTime } from '../../staff/time';
import { formatRwandanPhone } from '../../utils/phone';
import styles from '../../staff/staff.module.css';

function SmsOutbox() {
  const { t } = useI18n();
  const rows = useRequest(api.smsOutbox, { immediate: true, args: [] });

  return (
    <StaffLayout title={t('staff.nav.sms')} lede={t('staff.sms.lede')}>
      <section className="panel" aria-label={t('staff.nav.sms')}>
        <div className={styles.filters}>
          <Button variant="secondary" onClick={rows.retry} loading={rows.status === 'loading'}>
            {t('staff.sms.refresh')}
          </Button>
        </div>
        {rows.status === 'success' ? (
          rows.data.length === 0 ? (
            <p className={styles.empty}>{t('staff.sms.none')}</p>
          ) : (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">{t('staff.activity.col.when')}</th>
                    <th scope="col">{t('staff.sms.to')}</th>
                    <th scope="col">{t('staff.sms.message')}</th>
                    <th scope="col">{t('staff.col.status')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.data.map((m) => (
                    <tr key={m.id}>
                      <td className="code">{dateTime(m.at)}</td>
                      <td data-label={t('staff.sms.to')} className="code">
                        {formatRwandanPhone(m.phone)}
                      </td>
                      <td data-label={t('staff.sms.message')}>{m.message}</td>
                      <td data-label={t('staff.col.status')}>
                        <span className={m.status === 'sent' ? undefined : styles.flagged}>
                          {m.status === 'sent' ? t('staff.sms.sent') : m.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        ) : (
          <RequestState status={rows.status} error={rows.error} onRetry={rows.retry} />
        )}
      </section>
    </StaffLayout>
  );
}

export default SmsOutbox;
