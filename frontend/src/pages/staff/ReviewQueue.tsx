/**
 * @file ReviewQueue.tsx
 * @description Held readings, decided on one screen: the list on the
 * left, and for the selected reading the read digits on the meter counter,
 * the numbers a decision rests on, and the household's last readings.
 *
 * Keyboard: J / K next and previous, A accept, R reject, U undo.
 * A decision waits 5 seconds before it is sent, so it can be undone
 * (accepting creates a bill, which cannot be taken back once sent).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import StaffLayout from '../../components/StaffLayout/StaffLayout';
import RequestState, { errorMessage } from '../../components/RequestState/RequestState';
import MeterCounter from '../../components/MeterCounter/MeterCounter';
import Button from '../../components/Button/Button';
import Notice from '../../components/Notice/Notice';
import Icon from '../../components/Icon/Icon';
import { api } from '../../api/client';
import useRequest from '../../api/useRequest';
import type { ReviewItem } from '../../api/types';
import { useI18n } from '../../i18n/I18nProvider';
import useCounterLabels from '../../i18n/useCounterLabels';
import { cellsFromCubicMetres, formatReading } from '../../utils/reading';
import { ISSUE_KEY, previousReading, usualUse } from '../../staff/issues';
import styles from './ReviewQueue.module.css';

const UNDO_MS = 5000;
type Outcome = 'accept' | 'reject';

interface Pending {
  item: ReviewItem;
  outcome: Outcome;
}

function DecisionPane({ item }: { item: ReviewItem }) {
  const { t, locale, volume, date } = useI18n();
  const labels = useCounterLabels();
  const previous = previousReading(item.history);
  const usual = usualUse(item.history);
  const used = item.reading_m3 !== null && previous !== null ? item.reading_m3 - previous : null;
  const ratio = used !== null && usual ? used / usual : null;
  const months = [...item.history.slice(-5).map((h) => ({ key: h.date, label: date(h.date), m3: h.consumption_m3 ?? 0, current: false })),
    ...(used !== null ? [{ key: 'this', label: t('staff.review.thisReading'), m3: used, current: true }] : [])];
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
          {t(ISSUE_KEY[item.flag.anomaly_type])}
        </p>
      </div>

      <div className={styles.paneGrid}>
        <section className={styles.block} aria-labelledby="read-title">
          <h3 id="read-title" className={styles.blockTitle}>
            {t('staff.review.read')}
          </h3>
          {item.reading_m3 !== null ? (
            <MeterCounter cells={cellsFromCubicMetres(item.reading_m3)} labels={labels} size="small" locale={locale} />
          ) : (
            <p className="text-secondary">{t('staff.review.noReading')}</p>
          )}
          <dl className={styles.facts}>
            <div>
              <dt>{t('staff.review.previous')}</dt>
              <dd>{previous !== null ? `${formatReading(cellsFromCubicMetres(previous), locale)} m³` : '–'}</dd>
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
          </dl>
          <p className="text-small text-secondary">{t('staff.review.noPhoto')}</p>
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
                  <span className={styles.barValue}>{volume(m.m3)}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}

function ReviewQueue() {
  const { t, rwf } = useI18n();
  const [params, setParams] = useSearchParams();
  const queue = useRequest(api.reviewQueue, { immediate: true, args: [] });
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(() => Number(params.get('flag')) || null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const timer = useRef<number | null>(null);
  const pendingRef = useRef<Pending | null>(null);
  pendingRef.current = pending;
  const paneRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (queue.status === 'success') setItems(queue.data);
  }, [queue.status, queue.data]);

  const visible = items.filter((i) => i.flag.id !== pending?.item.flag.id);
  const selected = visible.find((i) => i.flag.id === selectedId) ?? visible[0] ?? null;

  const select = useCallback(
    (id: number, scroll = false) => {
      setSelectedId(id);
      setParams({ flag: String(id) }, { replace: true });
      if (scroll && !window.matchMedia?.('(min-width: 1100px)').matches) {
        paneRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },
    [setParams],
  );

  const send = useCallback(
    async ({ item, outcome }: Pending) => {
      setPending(null);
      try {
        const res = await api.resolveFlag(item.flag.id, outcome);
        setItems((list) => list.filter((i) => i.flag.id !== item.flag.id));
        const name = item.customer_name ?? item.flag.household_id;
        setResult(
          outcome === 'accept'
            ? res.amount_due !== null
              ? t('staff.review.acceptedBill', { name, amount: rwf(res.amount_due) })
              : t('staff.review.accepted', { name })
            : t('staff.review.rejected', { name }),
        );
      } catch (err) {
        setError(err);
      }
    },
    [t, rwf],
  );

  const decide = useCallback(
    (outcome: Outcome) => {
      if (!selected) return;
      if (pending) send(pending); // a second decision sends the first now
      setError(null);
      setResult(null);
      const next = visible[visible.indexOf(selected) + 1] ?? visible[visible.indexOf(selected) - 1];
      const decision = { item: selected, outcome };
      setPending(decision);
      if (next) setSelectedId(next.flag.id);
      if (timer.current) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => send(decision), UNDO_MS);
    },
    [selected, pending, visible, send],
  );

  const undo = useCallback(() => {
    if (!pending) return;
    if (timer.current) window.clearTimeout(timer.current);
    setSelectedId(pending.item.flag.id);
    setPending(null);
  }, [pending]);

  // Leaving the page sends a waiting decision rather than losing it.
  useEffect(
    () => () => {
      if (timer.current) window.clearTimeout(timer.current);
      const waiting = pendingRef.current;
      if (waiting) api.resolveFlag(waiting.item.flag.id, waiting.outcome).catch(() => undefined);
    },
    [],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (e.ctrlKey || e.metaKey || e.altKey || target?.closest('input, select, textarea')) return;
      const index = selected ? visible.indexOf(selected) : -1;
      const key = e.key.toLowerCase();
      const nextItem = visible[index + 1];
      const prevItem = index > 0 ? visible[index - 1] : undefined;
      if (key === 'j' && nextItem) select(nextItem.flag.id);
      else if (key === 'k' && prevItem) select(prevItem.flag.id);
      else if (key === 'a') decide('accept');
      else if (key === 'r') decide('reject');
      else if (key === 'u') undo();
      else return;
      e.preventDefault();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [visible, selected, select, decide, undo]);

  const count = visible.length;

  if (queue.status !== 'success') {
    return (
      <StaffLayout title={t('staff.nav.review')}>
        <RequestState status={queue.status} error={queue.error} onRetry={queue.retry} />
      </StaffLayout>
    );
  }

  return (
    <StaffLayout
      title={t('staff.nav.review')}
      lede={count ? t('staff.review.lede', { count }) : undefined}
      reviewCount={count}
    >
      <div className={styles.feedback} aria-live="polite">
        {pending && (
          <Notice
            tone="held"
            actions={
              <Button variant="secondary" onClick={undo}>
                {t('staff.review.undo')}
              </Button>
            }
          >
            {pending.outcome === 'accept'
              ? t('staff.review.accepting', { name: pending.item.customer_name ?? pending.item.flag.household_id })
              : t('staff.review.rejecting', { name: pending.item.customer_name ?? pending.item.flag.household_id })}
          </Notice>
        )}
        {result && !pending && <Notice tone="done">{result}</Notice>}
        {Boolean(error) && <Notice tone="error">{errorMessage(t, error)}</Notice>}
      </div>

      {count === 0 ? (
        <section className="panel">
          <h2 className="panel-title">{t('staff.review.emptyTitle')}</h2>
          <p className="text-secondary">{t('staff.review.empty')}</p>
        </section>
      ) : (
        <div className={styles.layout}>
          <section className={`panel ${styles.list}`} aria-labelledby="queue-title">
            <h2 id="queue-title" className={styles.blockTitle}>
              {t('staff.review.listTitle', { count })}
            </h2>
            <ul>
              {visible.map((item) => {
                const active = item.flag.id === selected?.flag.id;
                return (
                  <li key={item.flag.id}>
                    <button
                      type="button"
                      className={`${styles.item} ${active ? styles.itemActive : ''}`}
                      aria-current={active ? 'true' : undefined}
                      onClick={() => select(item.flag.id, true)}
                    >
                      <span className={styles.itemName}>{item.customer_name ?? item.flag.household_id}</span>
                      <span className={styles.itemIssue}>{t(ISSUE_KEY[item.flag.anomaly_type])}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
            <p className={`${styles.keys} text-small`}>{t('staff.review.keys')}</p>
          </section>

          {selected && (
            <section ref={paneRef} className={`panel ${styles.pane}`} aria-label={t('staff.review.decision')}>
              <DecisionPane item={selected} />
              <div className={styles.actions}>
                <Button onClick={() => decide('accept')} icon="check">
                  {t('staff.review.accept')}
                </Button>
                <Button variant="secondary" onClick={() => decide('reject')} icon="camera">
                  {t('staff.review.reject')}
                </Button>
              </div>
              <p className="text-small text-secondary">{t('staff.review.acceptNote')}</p>
            </section>
          )}
        </div>
      )}
    </StaffLayout>
  );
}

export default ReviewQueue;
