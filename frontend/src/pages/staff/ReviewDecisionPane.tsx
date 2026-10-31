/**
 * @file ReviewDecisionPane.tsx
 * @description What an officer sees about one held reading: the photo, the digits the reader and the
 * household gave, the numbers the decision rests on, and the household's last readings.
 */

import { useEffect, useState } from 'react';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import Icon from '../../components/Icon/Icon';
import { api } from '../../api/client';
import type { ReviewItem } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import { issueKey, previousReading, usualUse } from '../../staff/issues';
import { locationFinding } from '../../utils/location';
import styles from './ReviewQueue.module.css';

/** 1234 -> "1.2 km", 85 -> "85 m". */
function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

/** Already billed: nothing to accept or reject, only follow-up to close. */
export function isFollowUp(item: ReviewItem): boolean {
  return item.flag.reading_status !== 'pending_review';
}

/** The meter photo the reading came from, fetched with the staff token (an <img src> cannot send it). */
function ReadingPhoto({ readingId, name }: { readingId: number; name: string }) {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    let made: string | null = null;
    setUrl(null);
    setFailed(false);
    api
      .readingPhoto(readingId)
      .then((blob) => {
        if (!live) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [readingId]);
  if (failed) return <p className="text-small text-secondary">{t('staff.review.photoFailed')}</p>;
  if (!url) return <p className="text-small text-secondary">{t('staff.review.photoLoading')}</p>;
  return (
    <a href={url} target="_blank" rel="noreferrer" className={styles.photo}>
      <img src={url} alt={t('staff.review.photoAlt', { name })} />
    </a>
  );
}

/** The reader's digits and the household's, the wheels the household changed in bold. */
function DigitChange({ ai, typed, changed }: { ai: string; typed: string; changed: number[] }) {
  const { t } = useI18n();
  const show = (digits: string) =>
    digits.split('').map((d, i) => (changed.includes(i) ? <strong key={i} className={styles.strong}>{d}</strong> : <span key={i}>{d}</span>));
  return (
    <span className="code" aria-label={t('staff.review.changedWheels', { ai, typed })}>
      {show(ai)} → {show(typed)}
    </span>
  );
}

function DecisionPane({ item }: { item: ReviewItem }) {
  const { t, volume, date } = useI18n();
  const labels = useCounterLabels();
  const previous = item.previous_reading_m3 ?? previousReading(item.history);
  const usual = usualUse(item.history);
  const where = locationFinding(item.flag.features);
  const used = item.consumption_m3 ?? (item.reading_m3 !== null && previous !== null ? item.reading_m3 - previous : null);
  const ratio = used !== null && usual ? used / usual : null;
  const months = [...item.history.slice(-5).map((h) => ({ key: h.date, label: date(h.date), m3: h.consumption_m3 ?? 0, current: false, was: h.original_consumption_m3 ?? null })),
    ...(used !== null ? [{ key: 'this', label: t('staff.review.thisReading'), m3: used, current: true, was: null }] : [])];
  const max = Math.max(...months.map((m) => Math.abs(m.m3)), 1);

  return (
    <>
      <div className={styles.paneHead}>
        <div>
          <h2 className="panel-title">{item.customer_name ?? item.flag.household_id}</h2>
          <p className="text-secondary">
            {item.sector && <span>{item.sector}</span>}
            <span className="code">{item.flag.household_id}</span>
          </p>
        </div>
        <p className={styles.issue}>
          <Icon name="clock" size={20} />
          {t(issueKey(item.flag))}
        </p>
      </div>

      <div className={styles.paneGrid}>
        <section className={styles.block} aria-labelledby="read-title">
          <h3 id="read-title" className={styles.blockTitle}>
            {t('staff.review.read')}
          </h3>
          {item.reading_m3 !== null ? (
            <MeterCounter cells={cellsFromCubicMetres(item.reading_m3)} labels={labels} size="small" />
          ) : (
            <p className="text-secondary">{t('staff.review.noReading')}</p>
          )}
          <dl className={styles.facts}>
            {item.meter_serial && (
              <div>
                <dt>{t('staff.review.serial')}</dt>
                <dd className="code">{item.meter_serial}</dd>
              </div>
            )}
            <div>
              <dt>{t('staff.review.previous')}</dt>
              <dd>{previous !== null ? `${formatReading(cellsFromCubicMetres(previous))} m³` : '–'}</dd>
            </div>
            <div>
              <dt>{t('staff.review.used')}</dt>
              <dd className={used !== null && used < 0 ? styles.strong : undefined}>{used !== null ? volume(used) : '–'}</dd>
            </div>
            <div>
              <dt>{t('staff.review.usual')}</dt>
              <dd>{usual !== null ? volume(usual) : '–'}</dd>
            </div>
            {ratio !== null && ratio > 0 && (
              <div>
                <dt>{t('staff.review.ratio')}</dt>
                <dd className={ratio >= 2 ? styles.strong : undefined}>{t('staff.review.times', { n: ratio.toFixed(1) })}</dd>
              </div>
            )}
            {item.reader_digits && (
              <div>
                <dt>{t('staff.review.readerRead')}</dt>
                <dd>
                  {formatReading(cellsFromCubicMetres(Number(item.reader_digits) / 1000))} m³
                  {item.edited_by_household && <span className={styles.strong}> · {t('staff.review.edited')}</span>}
                </dd>
              </div>
            )}
            {item.reader_digits && item.household_digits && (item.changed_positions?.length ?? 0) > 0 && (
              <div>
                <dt>{t('staff.review.changed')}</dt>
                <dd>
                  <DigitChange ai={item.reader_digits} typed={item.household_digits} changed={item.changed_positions ?? []} />
                </dd>
              </div>
            )}
            {item.reading_confidence !== null && (
              <div>
                <dt>{t('staff.review.confidence')}</dt>
                <dd>{Math.round(item.reading_confidence * 100)}%</dd>
              </div>
            )}
            <div>
              <dt>{t('staff.review.sent')}</dt>
              <dd>{date(item.submitted_at ?? item.flag.created_at)}</dd>
            </div>
            {where && (
              <div>
                <dt>{t('staff.review.where')}</dt>
                <dd className={styles.strong}>
                  {t(`staff.review.where.${where.reason}`, {
                    distance: where.distanceM !== null ? formatDistance(where.distanceM) : '–',
                    accuracy: where.accuracyM !== null ? formatDistance(where.accuracyM) : '–',
                  })}
                  {where.lat !== null && where.lng !== null && (
                    <>
                      {' '}
                      <a
                        href={`https://www.openstreetmap.org/?mlat=${where.lat}&mlon=${where.lng}#map=18/${where.lat}/${where.lng}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {t('staff.review.openMap')}
                      </a>
                    </>
                  )}
                </dd>
              </div>
            )}
          </dl>
          {item.photo_available && item.reading_id ? (
            <ReadingPhoto readingId={item.reading_id} name={item.customer_name ?? item.flag.household_id} />
          ) : (
            <p className="text-small text-secondary">{t('staff.review.noPhoto')}</p>
          )}
        </section>

        <section className={styles.block} aria-labelledby="history-title">
          <h3 id="history-title" className={styles.blockTitle}>
            {t('staff.review.history')}
          </h3>
          {months.length === 0 ? (
            <p className="text-secondary">{t('staff.review.noHistory')}</p>
          ) : (
            <ol className={styles.bars}>
              {months.map((m) => (
                <li key={m.key} className={m.current ? styles.current : undefined}>
                  <span className={styles.barLabel}>{m.label}</span>
                  <span className={styles.track} aria-hidden="true">
                    <span className={styles.bar} style={{ width: `${(Math.max(m.m3, 0) / max) * 100}%` }} />
                  </span>
                  <span className={styles.barValue}>
                    {volume(m.m3)}
                    {m.was !== null && <span className="text-small"> {t('staff.review.correctedFrom', { volume: volume(m.was) })}</span>}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}

export default DecisionPane;
