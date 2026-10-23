/**
 * @file Overview.tsx
 * @description Staff overview: a welcome banner that says what needs a decision now, four
 * figures, open issues by type as a bar chart, what is waiting, and every household at a glance.
 */

import { Link } from 'react-router-dom';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState from '../../components/RequestState/RequestState';
import Icon from '../../components/Icon/Icon';
import useRequest from '../../api/useRequest';
import { useI18n } from '../../i18n/I18nProvider';
import { useAuth } from '../../staff/auth';
import { ISSUE_KEY } from '../../staff/issues';
import loadOverview from '../../staff/loadOverview';
import HouseholdTable from './HouseholdTable';
import styles from '../../staff/staff.module.css';

function Overview() {
  const { t, rwf, volume, date } = useI18n();
  const { user } = useAuth();
  const data = useRequest(loadOverview, { immediate: true, args: [] });
  const lede = user ? t('staff.overview.lede', { name: user.full_name }) : undefined;

  if (data.status !== 'success') {
    return (
      <StaffLayout title={t('staff.nav.overview')} lede={lede}>
        <RequestState status={data.status} error={data.error} onRetry={data.retry} />
      </StaffLayout>
    );
  }

  const { queue, openFlags, households, unpaidAmount, unpaidCount } = data.data;
  // Open issues by type, largest first (one series: bars in one colour, values labelled).
  const byType = Object.entries(
    openFlags.reduce<Record<string, number>>((acc, f) => ({ ...acc, [f.anomaly_type]: (acc[f.anomaly_type] ?? 0) + 1 }), {}),
  ).sort((a, b) => b[1] - a[1]);
  const most = Math.max(1, ...byType.map(([, n]) => n));

  return (
    <StaffLayout title={t('staff.nav.overview')} lede={lede} reviewCount={queue.length}>
      <section className={`${styles.welcome} imigongo-band`} aria-label={t('staff.overview.summary')}>
        <div>
          <p className={styles.welcomeTitle}>
            {queue.length ? t('staff.overview.welcomeWaiting', { count: queue.length }) : t('staff.overview.welcomeClear')}
          </p>
          <p className="text-secondary">{t('staff.overview.welcomeBody')}</p>
        </div>
        {queue.length > 0 && (
          <Link to="/staff/review" className={styles.welcomeCta}>
            {t('staff.overview.openQueue')}
            <Icon name="arrowRight" size={18} />
          </Link>
        )}
      </section>

      <section className={styles.stats} aria-label={t('staff.overview.summary')}>
        <Link to="/staff/review" className={`panel ${styles.stat} ${queue.length ? styles.attention : ''}`}>
          <span className={styles.statIcon} aria-hidden="true">
            <Icon name="queue" size={20} />
          </span>
          <span className={styles.statLabel}>{t('staff.stat.toReview')}</span>
          <span className={styles.statValue}>{queue.length}</span>
          <span className={styles.statNote}>{queue.length ? t('staff.stat.openQueue') : t('staff.stat.nothingWaiting')}</span>
        </Link>
        <div className={`panel ${styles.stat}`}>
          <span className={styles.statIcon} aria-hidden="true">
            <Icon name="alert" size={20} />
          </span>
          <span className={styles.statLabel}>{t('staff.stat.openFlags')}</span>
          <span className={styles.statValue}>{openFlags.length}</span>
          <span className={styles.statNote}>{t('staff.stat.openFlagsNote')}</span>
        </div>
        <div className={`panel ${styles.stat}`}>
          <span className={styles.statIcon} aria-hidden="true">
            <Icon name="households" size={20} />
          </span>
          <span className={styles.statLabel}>{t('staff.nav.households')}</span>
          <span className={styles.statValue}>{households.length}</span>
          <span className={styles.statNote}>
            {t('staff.stat.flaggedHouseholds', { count: households.filter((h) => h.anomaly_flagged).length })}
          </span>
        </div>
        <div className={`panel ${styles.stat}`}>
          <span className={styles.statIcon} aria-hidden="true">
            <Icon name="bills" size={20} />
          </span>
          <span className={styles.statLabel}>{t('staff.stat.unpaid')}</span>
          <span className={styles.statValue}>{rwf(unpaidAmount)}</span>
          <span className={styles.statNote}>{t('staff.stat.unpaidNote', { count: unpaidCount })}</span>
        </div>
      </section>

      <div className={styles.grid}>
        <section className="panel" aria-labelledby="waiting-title">
          <div className={styles.panelHead}>
            <h2 id="waiting-title" className="panel-title">
              {t('staff.overview.waiting')}
            </h2>
            {queue.length > 0 && <Link to="/staff/review">{t('staff.overview.openQueue')}</Link>}
          </div>
          {queue.length === 0 ? (
            <p className={styles.empty}>{t('staff.review.empty')}</p>
          ) : (
            <ul className={styles.queueList}>
              {queue.slice(0, 5).map((item) => (
                <li key={item.flag.id}>
                  <Link to={`/staff/review?flag=${item.flag.id}`} className={styles.queueRow}>
                    <span className={styles.queueName}>{item.customer_name ?? item.flag.household_id}</span>
                    <span className="num">{item.reading_m3 !== null ? volume(item.reading_m3) : ''}</span>
                    <span className={styles.flagged}>{t(ISSUE_KEY[item.flag.anomaly_type])}</span>
                    <span className="text-small text-secondary num">{date(item.flag.created_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-labelledby="issues-title">
          <div className={styles.panelHead}>
            <h2 id="issues-title" className="panel-title">
              {t('staff.overview.issuesTitle')}
            </h2>
            <span className="chip">{t('staff.overview.issuesOpen', { count: openFlags.length })}</span>
          </div>
          {byType.length === 0 ? (
            <p className={styles.empty}>{t('staff.overview.issuesNone')}</p>
          ) : (
            <ul className={styles.issueBars}>
              {byType.map(([type, n]) => (
                <li key={type} className={styles.issueRow}>
                  <span className={styles.issueName}>{t(ISSUE_KEY[type as keyof typeof ISSUE_KEY])}</span>
                  <span className={styles.issueTrack} aria-hidden="true">
                    <span className={styles.issueBar} style={{ width: `${(n / most) * 100}%` }} />
                  </span>
                  <span className={styles.issueValue}>{n}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className={`panel ${styles.wide}`} aria-labelledby="households-title">
          <div className={styles.panelHead}>
            <h2 id="households-title" className="panel-title">
              {t('staff.nav.households')}
            </h2>
            <Link to="/staff/households">{t('staff.overview.allHouseholds')}</Link>
          </div>
          <HouseholdTable households={households.slice(0, 6)} compact />
        </section>
      </div>
    </StaffLayout>
  );
}

export default Overview;
